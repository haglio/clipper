"""How the launcher's answer becomes a VideoState.

The three cases below used to patch `parse_timestamp` (pure string arithmetic),
`read_json`, `create_session` and `load_video_state` -- the function the caller
exists to call -- and then assert `create_session` had been handed a particular
argument tuple. That pins the call, not the session: it stays green if the
session written is wrong, and it goes red on an argument reshuffle that changes
nothing. Here only ffprobe and the decoder are stubbed; the JSON is written and
read back for real.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from clipper import create_session as create_session_module
from clipper import session_launch, state_factory
from clipper.app import main as app_main
from clipper.launch_choice import ClipWholeVideo, LoadSession, NewSession
from clipper.session_launch import build_clip_whole_state, build_state, launch_state


@pytest.fixture()
def library(tmp_path: Path, monkeypatch):
    """A sessions folder, a stubbed ffprobe and a decoder that answers."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    pointer = tmp_path / ".last_session.txt"

    monkeypatch.setattr(create_session_module, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(create_session_module, "LAST_SESSION_FILE", pointer)
    monkeypatch.setattr(session_launch, "LAST_SESSION_FILE", pointer)
    monkeypatch.setattr(
        create_session_module, "ffprobe_video_metadata", lambda path: (30.0, 900)
    )

    capture = MagicMock()
    capture.isOpened.return_value = True
    metadata = {cv2.CAP_PROP_FPS: 30.0, cv2.CAP_PROP_FRAME_COUNT: 900.0}
    capture.get.side_effect = metadata.get
    monkeypatch.setattr(state_factory.cv2, "VideoCapture", lambda path: capture)
    monkeypatch.setattr(
        state_factory,
        "load_range",
        lambda cap, start, end: {
            i: np.zeros((2, 2, 3), dtype=np.uint8) for i in range(start, end + 1)
        },
    )
    return SimpleNamespace(sessions=sessions, pointer=pointer)


def _write_session(sessions: Path, name: str, **overrides) -> Path:
    payload = {
        "version": 1,
        "session_name": name,
        "video_path": "/library/seaside walk.mp4",
        "fps": 30.0,
        "total_frames": 900,
        "loaded_start": 100,
        "loaded_end": 160,
        "active_start": 110,
        "active_end": 150,
        "current": 120,
        "seconds_per_step": 1.0,
        "loop_mode": "tip-base",
        "wrap_mode": "yellow",
        "speed": 1.25,
        "vr": False,
    }
    payload.update(overrides)
    path = sessions / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


class TestLoadingASavedSession:
    def test_the_state_comes_back_the_way_the_file_left_it(self, library):
        saved = _write_session(library.sessions, "seaside walk")

        state = build_state(LoadSession(session_json=str(saved)))

        assert state.session_name == "seaside walk"
        assert (state.active_start, state.active_end) == (110, 150)
        assert (state.loaded_start, state.loaded_end) == (100, 160)
        assert state.current == 120
        assert state.loop_mode == "tip-base"
        assert state.wrap_mode == "yellow"
        assert state.speed == pytest.approx(1.25)

    def test_it_is_guarded_as_existing_save_data_and_remembers_where_it_came_from(self, library):
        saved = _write_session(library.sessions, "seaside walk")

        state = build_state(LoadSession(session_json=str(saved)))

        assert state.session_path == str(saved)
        assert state.original_session_payload == json.loads(saved.read_text(encoding="utf-8"))
        assert state.protect_existing_save_data is True

    def test_it_becomes_the_session_the_launcher_offers_next_time(self, library):
        saved = _write_session(library.sessions, "seaside walk")

        build_state(LoadSession(session_json=str(saved)))

        assert library.pointer.read_text(encoding="utf-8") == str(saved)


class TestCreatingANewSession:
    def _new(self, **overrides):
        fields = {
            "video_file": "/library/seaside walk.mp4",
            "session_name": "second pass",
            "timestamp": "00:00:12.500",
            "seconds": 5.0,
            "loop_mode": "tip-base",
        }
        fields.update(overrides)
        return NewSession(**fields)

    def test_the_typed_timestamp_becomes_the_window_written_to_disk(self, library):
        state = build_state(self._new())

        written = json.loads((library.sessions / "second pass.json").read_text(encoding="utf-8"))
        assert written["active_start"] == 375  # 12.5s at 30fps
        assert written["active_end"] == 524  # plus five seconds, inclusive
        assert written["loop_mode"] == "tip-base"
        assert written["vr"] is False
        assert (state.active_start, state.active_end) == (375, 524)

    def test_an_hour_long_timestamp_is_parsed_whole(self, library):
        build_state(self._new(timestamp="00:00:20", seconds=1.0))

        written = json.loads((library.sessions / "second pass.json").read_text(encoding="utf-8"))
        assert written["active_start"] == 600

    def test_a_vr_session_is_marked_vr_in_the_file_and_on_the_state(self, library):
        state = build_state(self._new(vr=True))

        written = json.loads((library.sessions / "second pass.json").read_text(encoding="utf-8"))
        assert written["vr"] is True
        assert state.vr is True

    def test_it_is_guarded_as_existing_save_data_and_becomes_the_last_session(self, library):
        state = build_state(self._new())

        assert state.protect_existing_save_data is True
        assert library.pointer.read_text(encoding="utf-8") == str(
            library.sessions / "second pass.json"
        )

    def test_a_session_of_that_name_already_there_is_opened_rather_than_overwritten(self, library):
        existing = _write_session(library.sessions, "second pass", active_start=7, active_end=9)

        state = build_state(self._new())

        assert (state.active_start, state.active_end) == (7, 9)
        assert json.loads(existing.read_text(encoding="utf-8"))["active_start"] == 7


class TestBuildClipWholeState:
    """The lightweight state behind "Clip whole vid...": no frames, no editor."""

    @pytest.fixture()
    def whole(self):
        with patch("clipper.session_launch.ffprobe_video_metadata", return_value=(30.0, 300)), \
             patch("clipper.session_launch.cv2") as mock_cv2:
            mock_cv2.VideoCapture.return_value = MagicMock()
            yield build_clip_whole_state("/library/seaside walk.mp4")

    def test_the_range_covers_the_video_bar_its_duplicate_last_frame(self, whole):
        assert (whole.active_start, whole.active_end) == (0, 298)
        assert (whole.loaded_start, whole.loaded_end) == (0, 298)

    def test_it_loads_no_frames(self, whole):
        assert whole.frames == {}

    def test_it_skips_the_loop_post_process(self, whole):
        assert whole.skip_postprocess is True

    def test_the_session_takes_its_name_from_the_video(self, whole):
        assert whole.session_name == "seaside walk"

    def test_a_video_whose_name_cannot_be_a_filename_is_sanitized(self):
        with patch("clipper.session_launch.ffprobe_video_metadata", return_value=(30.0, 300)), \
             patch("clipper.session_launch.cv2") as mock_cv2:
            mock_cv2.VideoCapture.return_value = MagicMock()
            state = build_clip_whole_state("/library/take 1: second pass.mp4")

        assert state.session_name == "take 1_ second pass"


def test_a_canceled_launcher_gives_no_state_to_open():
    """Cancel used to raise `SystemExit(0)` out of a `-> VideoState | None`."""
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = 0  # QDialog.DialogCode.Rejected

    with patch("clipper.session_launch.ensure_runtime_dirs"), \
         patch("clipper.session_launch.LAST_SESSION_FILE", MagicMock(exists=MagicMock(return_value=False))), \
         patch("clipper.session_launch.LauncherDialog", return_value=mock_dialog), \
         patch("clipper.session_launch.detect_nau_session_prefill", return_value=None):
        assert launch_state() is None


def test_launch_state_runs_clip_whole_and_returns_none():
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = 1  # Accepted
    mock_dialog.build_result.return_value = ClipWholeVideo(video_file="/path/to/loop.mp4")

    with patch("clipper.session_launch.ensure_runtime_dirs"), \
         patch("clipper.session_launch.LAST_SESSION_FILE", MagicMock(exists=MagicMock(return_value=False))), \
         patch("clipper.session_launch.LauncherDialog", return_value=mock_dialog), \
         patch("clipper.session_launch.detect_nau_session_prefill", return_value=None), \
         patch("clipper.session_launch._run_clip_whole_export") as mock_export:
        result = launch_state()

    mock_export.assert_called_once_with("/path/to/loop.mp4")
    assert result is None


def test_launch_state_builds_state_from_launcher_info():
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = 1  # QDialog.DialogCode.Accepted
    chosen = LoadSession(session_json="/sessions/seaside walk.json")
    mock_dialog.build_result.return_value = chosen
    built_state = object()

    with patch("clipper.session_launch.ensure_runtime_dirs") as ensure_dirs, \
         patch("clipper.session_launch.LAST_SESSION_FILE", MagicMock(exists=MagicMock(return_value=False))), \
         patch("clipper.session_launch.LauncherDialog", return_value=mock_dialog), \
         patch("clipper.session_launch.detect_nau_session_prefill", return_value=None), \
         patch("clipper.session_launch.build_state", return_value=built_state) as open_it:
        result = launch_state()

    assert result is built_state
    ensure_dirs.assert_called_once_with()
    open_it.assert_called_once_with(chosen)


def test_app_main_returns_zero_when_launch_state_returns_none():
    with patch("clipper.app.launch_state", return_value=None), \
         patch("clipper.app._set_windows_app_user_model_id"), \
         patch("clipper.app._init_logger"):
        result = app_main()

    assert result == 0
