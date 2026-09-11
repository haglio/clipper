from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from clipper.session_persistence import (
    SESSION_FORMAT_VERSION,
    autosave_session,
    current_payload,
    safe_atomic_write_json,
)


def _state(**overrides):
    defaults = dict(
        session_name="demo",
        path="/video.mp4",
        fps=30.0,
        total_frames=120,
        loaded_start=10,
        loaded_end=40,
        active_start=12,
        active_end=30,
        current=18,
        base_step=30,
        loop_mode="base-tip-base",
        wrap_mode="blue",
        speed=1.25,
        vr=False,
        session_path="C:\\demo.json",
        session_warning="",
        last_saved_payload=None,
        original_session_payload={"version": 1},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_current_payload_builds_expected_fields():
    payload = current_payload(_state())

    assert payload == {
        "version": 1,
        "session_name": "demo",
        "video_path": "/video.mp4",
        "fps": 30.0,
        "total_frames": 120,
        "loaded_start": 10,
        "loaded_end": 40,
        "active_start": 12,
        "active_end": 30,
        "current": 18,
        "seconds_per_step": 1.0,
        "loop_mode": "base-tip-base",
        "wrap_mode": "blue",
        "speed": 1.25,
        "vr": False,
    }


def test_current_payload_includes_vr_true():
    payload = current_payload(_state(vr=True))
    assert payload["vr"] is True


class TestTheFieldsAnotherAppReads:
    """Evolver moves the videos this app cuts, so it walks `sessions/*.json`,
    repoints the reference in each and writes the file back whole.  Four keys
    are therefore its contract and not ours to rename quietly -- a rename that
    stopped here would strand every session it would have repointed, silently,
    since nothing over there imports this."""

    def test_a_session_says_which_shape_it_is(self):
        assert current_payload(_state())["version"] == SESSION_FORMAT_VERSION

    def test_the_video_it_was_cut_against_is_a_top_level_string(self):
        assert current_payload(_state())["video_path"] == "/video.mp4"

    def test_the_footage_is_described_well_enough_to_recognize_after_a_rename(self):
        """A video that was renamed rather than moved is nowhere to search for
        by name, and this pair is the only handle left on it."""
        payload = current_payload(_state())

        assert payload["fps"] == 30.0
        assert payload["total_frames"] == 120


def test_autosave_session_updates_last_saved_payload_on_success():
    state = _state()
    last_session_file = MagicMock()

    with patch("clipper.session_persistence.safe_atomic_write_json", return_value=(True, "")), \
         patch("clipper.session_persistence.LAST_SESSION_FILE", last_session_file):
        autosave_session(state)

    assert state.session_warning == ""
    assert state.last_saved_payload == current_payload(state)
    last_session_file.write_text.assert_called_once_with("C:\\demo.json", encoding="utf-8")


def test_autosave_session_records_failure_message():
    state = _state()

    with patch("clipper.session_persistence.safe_atomic_write_json", return_value=(False, "disk full")):
        autosave_session(state)

    assert state.session_warning == "Autosave failed: disk full"
    assert state.last_saved_payload is None


def test_a_failed_write_keeps_the_last_payload_that_did_reach_disk():
    """The warning is the only signal the user gets; the good payload stands.

    Driven through the real safe_atomic_write_json with nothing but the
    filesystem in the way -- the session path names a directory that is not
    there, which is the shape a moved or unmounted sessions folder takes.
    """
    good = {"version": 1, "session_name": "demo"}
    state = _state(session_path="/no/such/directory/demo.json", last_saved_payload=good)

    autosave_session(state)

    assert state.last_saved_payload == good
    assert state.session_warning.startswith("Autosave failed: ")
    assert "demo.json" in state.session_warning


def test_a_write_that_succeeds_clears_an_earlier_warning(tmp_path: Path):
    state = _state(session_path=str(tmp_path / "demo.json"),
                   session_warning="Autosave failed: disk full")

    autosave_session(state)

    assert state.session_warning == ""
    assert state.last_saved_payload == current_payload(state)
    assert (tmp_path / "demo.json").exists()


class TestSafeAtomicWriteJson:
    def test_writes_file(self, tmp_path: Path):
        target = tmp_path / "out.json"
        ok, err = safe_atomic_write_json(target, {"key": "value"})
        assert (ok, err) == (True, "")
        assert target.exists()

    def test_content_is_valid_json(self, tmp_path: Path):
        target = tmp_path / "out.json"
        safe_atomic_write_json(target, {"answer": 42})
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["answer"] == 42

    def test_no_tmp_file_left_after_success(self, tmp_path: Path):
        target = tmp_path / "out.json"
        safe_atomic_write_json(target, {"x": 1})
        tmp = target.with_suffix(target.suffix + ".tmp")
        assert not tmp.exists()

    def test_returns_empty_error_on_success(self, tmp_path: Path):
        target = tmp_path / "out.json"
        ok, err = safe_atomic_write_json(target, {})
        assert ok is True
        assert err == ""

    def test_overwrites_existing_file(self, tmp_path: Path):
        target = tmp_path / "out.json"
        safe_atomic_write_json(target, {"v": 1})
        safe_atomic_write_json(target, {"v": 2})
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["v"] == 2

    def test_returns_false_on_permission_error(self, tmp_path: Path):
        target = tmp_path / "out.json"
        with patch("builtins.open", side_effect=PermissionError("denied")):
            ok, err = safe_atomic_write_json(target, {})
        assert ok is False
        assert "denied" in err

    def test_refuses_a_path_whose_parent_does_not_exist(self, tmp_path: Path):
        """It does not mkdir -- that is the caller's job -- but it must say so.

        The autosave warning the user sees is built from nothing but this
        return value, so a failure reported as a success is a session that
        silently stops being written.
        """
        target = tmp_path / "nested" / "dir" / "out.json"

        ok, err = safe_atomic_write_json(target, {"x": 1})

        assert ok is False
        # The path is named separator-agnostically: on Windows CPython formats
        # the OSError filename with repr() (doubling backslashes) and it names
        # the .tmp path, so the full str(target) is not a substring there.
        assert target.name in err
        assert not target.exists()

    def test_reports_a_failed_rename_and_leaves_no_half_written_file(self, tmp_path: Path):
        target = tmp_path / "out.json"

        with patch("clipper.session_persistence.os.replace", side_effect=OSError("disk full")):
            ok, err = safe_atomic_write_json(target, {"x": 1})

        assert ok is False
        assert "disk full" in err
        assert not target.exists()
        assert not target.with_suffix(".json.tmp").exists()

    def test_a_tmp_file_it_cannot_clean_up_does_not_mask_the_failure(self, tmp_path: Path):
        target = tmp_path / "out.json"

        with patch("clipper.session_persistence.os.replace", side_effect=OSError("disk full")), \
             patch("pathlib.Path.unlink", side_effect=OSError("still locked")):
            ok, err = safe_atomic_write_json(target, {"x": 1})

        assert ok is False
        assert "disk full" in err
