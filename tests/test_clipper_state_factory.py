"""Tests for clipper.state_factory — opening a saved session."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from clipper.loop_modes import LOOP_MODE_BASE_TIP_BASE
from clipper.state_factory import load_video_state


def _build_capture(*, fps: float = 30.0, total_frames: float = 120.0) -> MagicMock:
    cap = MagicMock()
    cap.isOpened.return_value = True
    cap.get.side_effect = [fps, total_frames]
    return cap


def _payload(**overrides) -> dict:
    payload = {
        "version": 1,
        "session_name": "demo",
        "video_path": "/video.mp4",
        "fps": 30.0,
        "total_frames": 120,
        "loaded_start": 10,
        "loaded_end": 40,
        "active_start": 12,
        "active_end": 35,
        "current": 18,
        "seconds_per_step": 1.0,
        "loop_mode": "base-tip-base",
        "wrap_mode": "blue",
        "speed": 1.0,
        "vr": False,
    }
    payload.update(overrides)
    return payload


def _load(payload: dict, *, frames: dict | None = None, capture=None):
    if frames is None:
        frames = {i: np.zeros((2, 2, 3), dtype=np.uint8) for i in range(10, 41)}
    with patch("clipper.state_factory.cv2.VideoCapture",
               return_value=capture or _build_capture()):
        with patch("clipper.state_factory.load_range", return_value=frames):
            return load_video_state(payload, "the file stem")


def test_a_loop_mode_the_app_does_not_have_falls_back_to_the_default():
    state = _load(_payload(loop_mode="not-a-mode"))

    assert state.loop_mode == LOOP_MODE_BASE_TIP_BASE


def test_a_speed_past_the_ceiling_is_clamped_to_it():
    state = _load(_payload(speed=2.3))

    assert state.speed == pytest.approx(2.0)


def test_it_raises_when_the_session_interval_yields_no_frames():
    with pytest.raises(RuntimeError, match="No frames were extracted"):
        _load(_payload(), frames={})


def test_a_session_written_before_vr_existed_reads_as_not_vr():
    """`vr` was added to the format after it shipped, so an older file has no
    such key and must not stop opening."""
    payload = _payload()
    del payload["vr"]

    state = _load(payload)

    assert state.vr is False


def test_it_loads_vr_from_the_payload():
    state = _load(_payload(vr=True))

    assert state.vr is True


def test_a_payload_with_no_name_of_its_own_takes_the_caller_s():
    payload = _payload()
    del payload["session_name"]

    state = _load(payload)

    assert state.session_name == "the file stem"
