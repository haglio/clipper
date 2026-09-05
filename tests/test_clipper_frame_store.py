from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from clipper.frame_store import (
    ensure_loaded,
    load_range,
    safe_frame,
    signature_for_index,
)


def test_load_range_returns_empty_when_end_before_start():
    cap = MagicMock()

    result = load_range(cap, 10, 5)

    assert result == {}
    cap.set.assert_not_called()
    cap.read.assert_not_called()


class _DamagedAt:
    """A decoder that cannot produce one frame and reads past it fine."""

    def __init__(self, bad: int):
        self._bad = bad
        self._pos = 0
        self.seeks: list[int] = []

    def set(self, prop, value) -> bool:
        self._pos = int(value)
        self.seeks.append(self._pos)
        return True

    def read(self):
        if self._pos == self._bad:
            return False, None
        self._pos += 1
        return True, np.zeros((2, 2, 3), dtype=np.uint8)


class _EndsAt:
    """A decoder that gives up for good after a frame, as a truncated file does."""

    def __init__(self, last: int):
        self._last = last
        self._pos = 0
        self.seeks: list[int] = []

    def set(self, prop, value) -> bool:
        self._pos = int(value)
        self.seeks.append(self._pos)
        return True

    def read(self):
        if self._pos > self._last:
            return False, None
        self._pos += 1
        return True, np.zeros((2, 2, 3), dtype=np.uint8)


def test_load_range_gets_past_a_frame_the_decoder_cannot_produce():
    """One damaged frame used to end the whole load, and `extend_right` faked
    the edge past it to force the next seek beyond (bug 55).  The loader seeks
    past a failed read itself, so the damaged frame alone is missing."""
    cap = _DamagedAt(62)

    result = load_range(cap, 61, 65)

    assert sorted(result) == [61, 63, 64, 65]
    assert cap.seeks == [61, 63]


def test_load_range_gives_up_on_a_file_that_has_ended():
    """Past a truncation every read fails; the retries are bounded, so the
    loader answers with what it got rather than seeking forever."""
    cap = _EndsAt(62)

    result = load_range(cap, 61, 300)

    assert sorted(result) == [61, 62]
    assert len(cap.seeks) <= 10


def test_ensure_loaded_expands_missing_edges_and_bumps_render_rev(make_state):
    state = make_state(loaded_start=10, loaded_end=20)
    left_frames = {i: np.full((2, 2, 3), i, dtype=np.uint8) for i in range(5, 10)}
    right_frames = {i: np.full((2, 2, 3), i, dtype=np.uint8) for i in range(21, 26)}

    with patch("clipper.frame_store.load_range", side_effect=[left_frames, right_frames]) as load:
        ensure_loaded(state, 5, 25)

    assert state.loaded_start == 5
    assert state.loaded_end == 25
    assert state.render_rev == 1
    assert state.frames[5].shape == (2, 2, 3)
    assert state.frames[25].shape == (2, 2, 3)
    load.assert_any_call(state.cap, 5, 9)
    load.assert_any_call(state.cap, 21, 25)


def test_ensure_loaded_is_noop_when_requested_range_is_already_loaded(make_state):
    state = make_state(loaded_start=10, loaded_end=20)

    with patch("clipper.frame_store.load_range") as load:
        ensure_loaded(state, 12, 18)

    assert state.loaded_start == 10
    assert state.loaded_end == 20
    assert state.render_rev == 0
    load.assert_not_called()


def test_safe_frame_loads_missing_index_on_demand(make_state):
    state = make_state(loaded_start=10, loaded_end=20)
    missing_frame = np.ones((2, 2, 3), dtype=np.uint8)
    state.frames.pop(25, None)

    def fake_ensure_loaded(target_state, want_start: int, want_end: int) -> None:
        assert target_state is state
        assert (want_start, want_end) == (25, 25)
        state.frames[25] = missing_frame

    with patch("clipper.frame_store.ensure_loaded", side_effect=fake_ensure_loaded) as ensure:
        frame = safe_frame(state, 25)

    assert frame is missing_frame
    ensure.assert_called_once_with(state, 25, 25)


def test_safe_frame_raises_when_on_demand_load_still_fails(make_state):
    state = make_state()
    state.frames.pop(35, None)

    with patch("clipper.frame_store.ensure_loaded"):
        with pytest.raises(RuntimeError, match="Could not load frame 35"):
            safe_frame(state, 35)


def test_signature_for_index_caches_processed_signature(make_state):
    state = make_state()
    cached_signature = np.ones((3, 3), dtype=np.float32)

    with patch("clipper.frame_store.preprocess_frame_signature", return_value=cached_signature) as preprocess:
        first = signature_for_index(state, 20)
        second = signature_for_index(state, 20)

    assert first is cached_signature
    assert second is cached_signature
    preprocess.assert_called_once()
