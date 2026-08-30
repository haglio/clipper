"""The session file evolver rewrites, loaded and saved back byte for byte.

``VideoState``'s field names *are* the version-1 session-JSON keys, and
``evolver/util/reference_stores.py`` enumerates this directory and rewrites
``video_path`` in place.  So every extraction out of ``VideoState`` has to sit
behind the payload builder and leave the file alone: same keys, same order,
same spellings, same trailing newline.

The golden text below is a literal, not something the code produced -- a test
that compares the app's output against the app's own output cannot see the two
drifting together.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

# A fabricated session, in the byte layout safe_atomic_write_json produces:
# json.dump(payload, indent=2) followed by one newline.
GOLDEN_SESSION = """{
  "version": 1,
  "session_name": "beta rehearsal",
  "video_path": "D:/media/example/beta rehearsal.mp4",
  "fps": 30.0,
  "total_frames": 480,
  "loaded_start": 60,
  "loaded_end": 210,
  "active_start": 90,
  "active_end": 150,
  "current": 120,
  "seconds_per_step": 1.0,
  "loop_mode": "base-tip",
  "wrap_mode": "blue",
  "speed": 1.25,
  "vr": true
}
"""


class _StubCapture:
    """The slice of cv2.VideoCapture the session loader reaches for.

    Wider than conftest's ``_FakeCapture``: ``load_video_state`` asks the
    capture for its own fps and frame count before it reads a frame.
    """

    def __init__(self, fps: float, total_frames: int):
        self._fps = fps
        self._total = total_frames
        self._pos = 0

    def isOpened(self) -> bool:  # noqa: N802 -- cv2 spells it this way
        return True

    def get(self, prop):
        import cv2

        return {cv2.CAP_PROP_FPS: self._fps,
                cv2.CAP_PROP_FRAME_COUNT: float(self._total)}[prop]

    def set(self, prop, value) -> bool:
        self._pos = int(value)
        return True

    def read(self):
        if self._pos >= self._total:
            return False, None
        self._pos += 1
        return True, np.zeros((4, 4, 3), dtype=np.uint8)

    def release(self) -> None:
        pass


@pytest.fixture()
def session_file(tmp_path: Path) -> Path:
    path = tmp_path / "beta rehearsal.json"
    path.write_text(GOLDEN_SESSION, encoding="utf-8")
    return path


@pytest.fixture()
def load_session(session_file):
    """Open the golden session through the launcher's own load path."""
    from clipper.launch_choice import LoadSession
    from clipper.session_launch import build_state

    def load():
        golden = json.loads(GOLDEN_SESSION)
        capture = _StubCapture(golden["fps"], golden["total_frames"])
        with patch("clipper.state_factory.cv2.VideoCapture", return_value=capture):
            return build_state(LoadSession(session_json=str(session_file)))

    return load


def test_the_two_writers_of_this_format_agree_on_it(make_state):
    """One builder makes the file, another rewrites it on every edit.

    They were two hand-written dict literals with no test comparing them, and
    a third copy had already drifted -- `state_factory`'s, which omitted `vr`,
    the key that decides which directory the clip is exported to.  An added key
    or a moved one now has to be made in both, or this fails.
    """
    from clipper.create_session import build_session_payload
    from clipper.session_persistence import current_payload

    created = build_session_payload(
        "D:/media/example/beta rehearsal.mp4", 2.0, 30.0, 480,
        session_name="beta rehearsal", seconds=5.0, loop_mode="base-tip", vr=True,
    )
    saved = current_payload(make_state())

    assert list(created) == list(saved) == list(json.loads(GOLDEN_SESSION))


def test_a_session_file_survives_a_load_and_a_save_byte_for_byte(session_file, load_session):
    state = load_session()

    state.autosave_session()

    assert session_file.read_text(encoding="utf-8") == GOLDEN_SESSION


def test_an_edit_rewrites_the_values_and_nothing_else(session_file, load_session):
    """An edited session keeps every key, in order -- only the values move."""
    from clipper.editing import set_mark_in

    state = load_session()
    set_mark_in(state)  # current (120) becomes the new active_start (was 90)

    saved = json.loads(session_file.read_text(encoding="utf-8"))
    golden = json.loads(GOLDEN_SESSION)

    assert list(saved) == list(golden)
    assert saved["active_start"] == 120
    assert {k: v for k, v in saved.items() if k != "active_start"} == {
        k: v for k, v in golden.items() if k != "active_start"
    }
