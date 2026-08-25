"""The candidate window the loop-point search walks.

`clipper/suggestion_search.py` is reached only through `loop_suggestions`, and
the word `direction` -- the parameter that decides which way the window runs --
appeared nowhere in tests/ until this file.
"""
from __future__ import annotations

import numpy as np
import pytest

from clipper.suggestion_search import candidate_similarity_curve, smooth_1d


def _signature(state, idx):
    """A stand-in for frame_store.signature_for_index: one number per frame."""
    return np.full((4, 4), idx / 100.0, dtype=np.float32)


def _score(a, b):
    return 1.0 - float(abs(a.mean() - b.mean()))


def _curve(state, ref_idx, direction):
    return candidate_similarity_curve(
        state, ref_idx, direction=direction,
        signature_for_index=_signature,
        structural_similarity_score=_score,
    )


class TestSmooth1d:
    def test_a_radius_of_zero_returns_the_values_untouched(self):
        values = np.array([1.0, 5.0, 1.0])

        assert list(smooth_1d(values, 0)) == [1.0, 5.0, 1.0]

    def test_it_does_not_write_into_what_it_was_given(self):
        values = np.array([1.0, 5.0, 1.0])

        smooth_1d(values, 1)

        assert list(values) == [1.0, 5.0, 1.0]

    def test_it_averages_each_point_with_its_neighbours(self):
        values = np.array([0.0, 0.0, 3.0, 0.0, 0.0])

        smoothed = smooth_1d(values, 1)

        assert len(smoothed) == 5
        assert smoothed[2] == pytest.approx(1.0)
        assert smoothed.max() == pytest.approx(1.0)


class TestTheCandidateWindow:
    def test_it_starts_ten_frames_clear_of_the_reference(self, make_state):
        """A loop shorter than the minimum gap is not a loop."""
        state = make_state(total_frames=200, loaded_start=0, loaded_end=120)

        candidates, _smoothed = _curve(state, 40, direction=+1)

        assert candidates[0] == 50
        assert candidates[-1] == 120

    def test_there_is_no_curve_when_the_window_holds_too_few_frames(self, make_state):
        state = make_state(total_frames=200, loaded_start=0, loaded_end=52)

        assert _curve(state, 40, direction=+1) is None

    def test_there_is_no_curve_when_the_window_is_empty(self, make_state):
        state = make_state(total_frames=200, loaded_start=0, loaded_end=45)

        assert _curve(state, 40, direction=+1) is None


class TestTheBackwardWindowRunsFromTheFarEnd:
    """HELD, not fixed: the two directions are not mirror images.

    Searching forward, candidate 0 is the frame just past the reference and the
    list runs away from it. Searching backward, candidate 0 is `loaded_start` --
    the frame *farthest* from the reference -- and the list runs towards it. The
    dip and peak walks in `best_turning_point_index` and
    `best_duplicate_match_index` skip a fixed head of that list and take their
    baseline from it, which forward means "the frames beside the reference" and
    backward means "the frames at the other end of the loaded range". In
    base-tip-base, the most common mode, that is where the suggested mark-in
    point comes from. Backlog bug 14 (`all/design/004`), awaiting sign-off;
    pinned so the fix is a visible change.
    """

    def test_forward_the_window_begins_next_to_the_reference(self, make_state):
        state = make_state(total_frames=200, loaded_start=20, loaded_end=120)

        candidates, _smoothed = _curve(state, 60, direction=+1)

        assert candidates[0] == 70  # the reference plus the minimum gap
        assert candidates[-1] == 120  # and it ends at the far edge

    def test_backward_the_window_begins_at_the_far_edge_instead(self, make_state):
        state = make_state(total_frames=200, loaded_start=20, loaded_end=120)

        candidates, _smoothed = _curve(state, 60, direction=-1)

        assert candidates[0] == 20  # loaded_start, farthest from the reference
        assert candidates[-1] == 50  # and it ends beside it

    def test_the_two_directions_are_not_reverses_of_each_other(self, make_state):
        state = make_state(total_frames=200, loaded_start=20, loaded_end=120)

        forward, _f = _curve(state, 60, direction=+1)
        backward, _b = _curve(state, 60, direction=-1)

        assert forward[0] - 60 == 10
        assert backward[0] - 60 == -40  # not -10, which a mirror image would give
