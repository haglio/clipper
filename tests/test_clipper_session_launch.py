from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from clipper.session_launch import build_state_from_launch_info, launch_state


def test_build_state_from_launch_info_loads_saved_session():
    state = SimpleNamespace(
        session_path="",
        original_session_payload={},
        protect_existing_save_data=False,
    )
    payload = {
        "video_path": "/video.mp4",
        "session_name": "demo",
        "loaded_start": 0,
        "loaded_end": 10,
        "active_start": 1,
        "active_end": 9,
        "current": 1,
        "seconds_per_step": 1.0,
        "fps": 30.0,
        "total_frames": 100,
    }

    last_session_file = MagicMock()

    with patch("clipper.session_launch.read_json", return_value=payload), \
         patch("clipper.session_launch.make_video_state", return_value=state), \
         patch("clipper.session_launch.LAST_SESSION_FILE", last_session_file):
        result = build_state_from_launch_info({"mode": "load", "session_json": "C:\\demo.json"})

    assert result is state
    assert state.session_path == "C:\\demo.json"
    assert state.original_session_payload == payload
    assert state.protect_existing_save_data is True
    last_session_file.write_text.assert_called_once_with("C:\\demo.json", encoding="utf-8")


def test_build_state_from_launch_info_creates_new_session_via_create_session():
    session_path = Path("C:\\sessions\\demo.json")
    payload = {
        "video_path": "/video.mp4",
        "session_name": "demo",
        "loaded_start": 375,
        "loaded_end": 524,
        "active_start": 375,
        "active_end": 524,
        "current": 375,
        "seconds_per_step": 1.0,
        "fps": 30.0,
        "total_frames": 900,
    }
    state = SimpleNamespace(
        session_path="",
        original_session_payload={},
        protect_existing_save_data=False,
    )
    last_session_file = MagicMock()

    with patch("clipper.session_launch.parse_timestamp", return_value=12.5), \
         patch("clipper.session_launch.create_session", return_value=session_path) as mock_create, \
         patch("clipper.session_launch.read_json", return_value=payload), \
         patch("clipper.session_launch.make_video_state", return_value=state) as make_state, \
         patch("clipper.session_launch.LAST_SESSION_FILE", last_session_file):
        result = build_state_from_launch_info(
            {
                "mode": "new",
                "video_file": "/video.mp4",
                "session_name": "demo",
                "timestamp": "00:00:12.5",
                "seconds": 5.0,
                "loop_mode": "tip-base",
            }
        )

    mock_create.assert_called_once_with(
        "/video.mp4", 12.5, session_name="demo", seconds=5.0, loop_mode="tip-base",
    )
    assert result is state
    assert state.session_path == str(session_path)
    assert state.original_session_payload == payload
    assert state.protect_existing_save_data is True
    last_session_file.write_text.assert_called_once()


def test_launch_state_raises_system_exit_when_launcher_is_cancelled():
    with patch("clipper.session_launch.ensure_runtime_dirs"), \
         patch("clipper.session_launch.launcher_dialog", return_value={"ok": False}):
        with pytest.raises(SystemExit) as excinfo:
            launch_state()

    assert excinfo.value.code == 0


def test_launch_state_builds_state_from_launcher_info():
    built_state = object()

    with patch("clipper.session_launch.ensure_runtime_dirs") as ensure_dirs, \
         patch("clipper.session_launch.launcher_dialog", return_value={"ok": True, "mode": "new"}), \
         patch("clipper.session_launch.build_state_from_launch_info", return_value=built_state) as build_state:
        result = launch_state()

    assert result is built_state
    ensure_dirs.assert_called_once_with()
    build_state.assert_called_once_with({"ok": True, "mode": "new"})
