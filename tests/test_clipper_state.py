"""Tests for clipper.state (pure logic, no real video files)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from clipper.editing import (
    accept_suggested_in,
    accept_suggested_out,
    cycle_loop_mode,
    set_mark_in,
    set_mark_out,
    shift_active_range,
)
from clipper.loaded_bounds import (
    contract_left,
    contract_right,
    extend_left,
    extend_right,
)
from clipper.loop_suggestions import update_loop_suggestions
from clipper.navigation import (
    move_current_left,
    move_current_right,
    toggle_wrap_mode,
)
from clipper.playback import (
    change_speed,
    current_loop_frame_index,
    loop_preview_indices,
    toggle_loop_pause,
)
from clipper.state import VideoState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pattern_frame(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(40, 40, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# VideoState computed properties
# ---------------------------------------------------------------------------

class TestVideoStateDefaults:
    def test_skip_postprocess_defaults_false(self, make_state):
        s = make_state()
        assert s.skip_postprocess is False



class TestVideoStateProperties:
    def test_loaded_count(self, make_state):
        s = make_state(loaded_start=0, loaded_end=49)
        assert s.loaded_count == 50

    def test_loaded_count_single_frame(self, make_state):
        s = make_state(loaded_start=5, loaded_end=5)
        assert s.loaded_count == 1

    def test_should_prompt_on_exit_only_for_existing_saved_data(self, make_state):
        s = make_state()
        s.dirty = True
        assert s.should_prompt_on_exit is False

        s.protect_existing_save_data = True
        assert s.should_prompt_on_exit is True

    def test_should_not_prompt_when_clean_even_for_loaded_sessions(self, make_state):
        s = make_state()
        s.protect_existing_save_data = True
        s.dirty = False
        assert s.should_prompt_on_exit is False


# ---------------------------------------------------------------------------
# clamp_current
# ---------------------------------------------------------------------------

class TestClampCurrent:
    def test_clamped_up_to_loaded_start_in_blue_mode(self, make_state):
        s = make_state(loaded_start=10, current=5, wrap_mode="blue")
        s.clamp_current()
        assert s.current == s.loaded_start

    def test_clamped_down_to_loaded_end_in_blue_mode(self, make_state):
        s = make_state(loaded_end=50, current=99, wrap_mode="blue")
        s.clamp_current()
        assert s.current == s.loaded_end

    def test_within_range_unchanged(self, make_state):
        s = make_state(loaded_start=0, loaded_end=99, current=50, wrap_mode="blue")
        s.clamp_current()
        assert s.current == 50


# ---------------------------------------------------------------------------
# current_payload
# ---------------------------------------------------------------------------

class TestCurrentPayload:
    def test_has_required_keys(self, make_state):
        s = make_state()
        payload = s.current_payload()
        for key in ("version", "session_name", "video_path", "fps", "total_frames",
                    "loaded_start", "loaded_end", "active_start", "active_end",
                    "current", "seconds_per_step", "loop_mode", "wrap_mode", "speed"):
            assert key in payload, f"Missing key: {key}"

    def test_version_is_1(self, make_state):
        s = make_state()
        assert s.current_payload()["version"] == 1

    def test_session_name_correct(self, make_state):
        s = make_state(session_name="my_clip")
        assert s.current_payload()["session_name"] == "my_clip"

    def test_seconds_per_step(self, make_state):
        s = make_state(base_step=30, fps=30.0)
        assert s.current_payload()["seconds_per_step"] == pytest.approx(1.0)

    def test_wrap_mode_preserved(self, make_state):
        s = make_state(wrap_mode="red")
        assert s.current_payload()["wrap_mode"] == "red"

    def test_loop_mode_preserved(self, make_state):
        s = make_state(loop_mode="tip-base")
        assert s.current_payload()["loop_mode"] == "tip-base"


class TestCycleLoopMode:
    def test_cycles_to_next_mode(self, make_state):
        s = make_state(loop_mode="base-tip-base")
        cycle_loop_mode(s)
        assert s.loop_mode == "tip-base-tip"


class TestToggleWrapMode:
    def test_switching_to_yellow_clamps_current_into_active_range(self, make_state):
        s = make_state(wrap_mode="blue", active_start=10, active_end=20, current=25)
        toggle_wrap_mode(s)
        assert s.wrap_mode == "yellow"
        assert s.current == 20

    def test_switching_back_to_blue_preserves_current(self, make_state):
        s = make_state(wrap_mode="yellow", active_start=10, active_end=20, current=15)
        toggle_wrap_mode(s)
        assert s.wrap_mode == "blue"
        assert s.current == 15


class TestMoveCurrent:
    def test_move_left_wraps_within_loaded_range_in_blue_mode(self, make_state):
        s = make_state(loaded_start=10, loaded_end=20, current=10, wrap_mode="blue")
        move_current_left(s)
        assert s.current == 20
        assert s.render_rev == 1

    def test_move_left_wraps_within_active_range_in_yellow_mode(self, make_state):
        s = make_state(loaded_start=0, loaded_end=30, active_start=10, active_end=20, current=10, wrap_mode="yellow")
        move_current_left(s)
        assert s.current == 20
        assert s.render_rev == 1

    def test_move_right_wraps_within_loaded_range_in_blue_mode(self, make_state):
        s = make_state(loaded_start=10, loaded_end=20, current=20, wrap_mode="blue")
        move_current_right(s)
        assert s.current == 10
        assert s.render_rev == 1

    def test_move_right_wraps_within_active_range_in_yellow_mode(self, make_state):
        s = make_state(loaded_start=0, loaded_end=30, active_start=10, active_end=20, current=20, wrap_mode="yellow")
        move_current_right(s)
        assert s.current == 10
        assert s.render_rev == 1


class TestLoopPause:
    def test_current_loop_frame_stays_fixed_while_paused(self, make_state):
        s = make_state(active_start=10, active_end=19, fps=10.0, speed=1.0,
                       loop_anchor=100.0)
        with patch("clipper.playback.time.monotonic", side_effect=[100.45, 100.8, 100.9]):
            toggle_loop_pause(s)
            first = current_loop_frame_index(s)
            second = current_loop_frame_index(s)
        assert s.loop_paused is True
        assert first == 14
        assert second == 14

    def test_toggle_pause_resume_keeps_same_frame_continuity(self, make_state):
        s = make_state(active_start=10, active_end=19, fps=10.0, speed=1.0,
                       loop_anchor=100.0)
        with patch("clipper.playback.time.monotonic", side_effect=[100.45, 100.45, 100.65]):
            toggle_loop_pause(s)
            toggle_loop_pause(s)
            resumed = current_loop_frame_index(s)
        assert s.loop_paused is False
        assert resumed == 16


class TestLoopPreviewIndices:
    def test_base_tip_preview_mirrors_back(self, make_state):
        s = make_state(active_start=10, active_end=12, loop_mode="base-tip")
        assert loop_preview_indices(s) == [10, 11, 12, 11, 10]

    def test_tip_base_preview_prepends_reversed_half(self, make_state):
        s = make_state(active_start=10, active_end=12, loop_mode="tip-base")
        assert loop_preview_indices(s) == [12, 11, 10, 11, 12]

    def test_tip_base_tip_preview_rotates_halfway(self, make_state):
        s = make_state(active_start=10, active_end=15, loop_mode="tip-base-tip")
        assert loop_preview_indices(s) == [13, 14, 15, 10, 11, 12]


class TestChangeSpeed:
    def test_speed_does_not_drop_below_quarter_x(self, make_state):
        s = make_state(speed=0.25)
        with patch("clipper.playback.time.monotonic", return_value=100.0):
            change_speed(s, -0.25)
        assert s.speed == pytest.approx(0.25)

    def test_change_speed_while_paused_keeps_paused_state(self, make_state):
        s = make_state(active_start=10, active_end=19, fps=10.0, speed=1.0,
                       loop_paused=True, paused_loop_idx=14)
        with patch("clipper.playback.time.monotonic", return_value=100.0):
            change_speed(s, 0.25)
        assert s.loop_paused is True
        assert s.loop.paused_idx == 14
        assert s.speed == pytest.approx(1.25)


# ---------------------------------------------------------------------------
# contract_left / extend_left / contract_right / extend_right
# ---------------------------------------------------------------------------

class TestContractLeft:
    def test_shrinks_loaded_start_by_base_step(self, make_state):
        s = make_state(loaded_start=10, active_start=20, base_step=5)
        contract_left(s)
        assert s.loaded_start == 15

    def test_prunes_frames_and_signatures_before_new_loaded_start(self, make_state):
        s = make_state(loaded_start=10, active_start=20, base_step=5)
        s.frames = {i: np.zeros((2, 2, 3), dtype=np.uint8) for i in range(10, 31)}
        s.frame_signatures = {i: np.zeros((2, 2), dtype=np.float32) for i in range(10, 31)}

        contract_left(s)

        assert s.loaded_start == 15
        assert all(idx >= 15 for idx in s.frames)
        assert all(idx >= 15 for idx in s.frame_signatures)

    def test_does_nothing_when_gap_too_small(self, make_state):
        s = make_state(loaded_start=0, active_start=3, base_step=5)
        s.frames = {i: np.zeros((2, 2, 3), dtype=np.uint8) for i in range(0, 100)}
        original = s.loaded_start
        contract_left(s)
        assert s.loaded_start == original

    def test_current_clamped_upward(self, make_state):
        s = make_state(loaded_start=0, active_start=20, base_step=5, current=3)
        contract_left(s)
        assert s.current >= s.loaded_start


class TestExtendLeft:
    """The other half of loaded_bounds: `a` widens the range the cursor roams.

    Both extend functions were imported by this file and tested by neither, so
    `clipper/loaded_bounds.py` sat at the lowest coverage of the pure-logic
    modules.
    """

    def test_widens_the_loaded_range_by_one_step(self, make_state):
        s = make_state(loaded_start=20, loaded_end=60, base_step=5)

        extend_left(s)

        assert s.loaded_start == 15

    def test_it_loads_the_frames_it_just_made_room_for(self, make_state):
        s = make_state(loaded_start=20, loaded_end=60, base_step=5)

        extend_left(s)

        assert all(idx in s.frames for idx in range(15, 20))

    def test_it_stops_at_the_start_of_the_video(self, make_state):
        s = make_state(loaded_start=2, loaded_end=60, base_step=5)

        extend_left(s)

        assert s.loaded_start == 0

    def test_at_the_start_of_the_video_it_still_saves(self, make_state):
        """It marks dirty unconditionally -- there is nowhere to go, but the
        session is written anyway."""
        s = make_state(loaded_start=0, loaded_end=60, base_step=5)

        extend_left(s)

        assert s.loaded_start == 0
        assert s.dirty is True


class TestExtendRight:
    def test_widens_the_loaded_range_by_one_step(self, make_state):
        s = make_state(total_frames=100, loaded_start=0, loaded_end=60, base_step=5)

        extend_right(s)

        assert s.loaded_end == 65

    def test_it_loads_the_frames_it_just_made_room_for(self, make_state):
        s = make_state(total_frames=100, loaded_start=0, loaded_end=60, base_step=5)

        extend_right(s)

        assert all(idx in s.frames for idx in range(61, 66))

    def test_it_stops_at_the_end_of_the_video(self, make_state):
        s = make_state(total_frames=100, loaded_start=0, loaded_end=97, base_step=5)

        extend_right(s)

        assert s.loaded_end == 99


class TestContractRight:
    def test_shrinks_loaded_end(self, make_state):
        s = make_state(loaded_end=99, active_end=70, base_step=5)
        contract_right(s)
        assert s.loaded_end == 94

    def test_prunes_frames_and_signatures_after_new_loaded_end(self, make_state):
        s = make_state(loaded_start=0, loaded_end=30, active_end=20, base_step=5)
        s.frames = {i: np.zeros((2, 2, 3), dtype=np.uint8) for i in range(0, 31)}
        s.frame_signatures = {i: np.zeros((2, 2), dtype=np.float32) for i in range(0, 31)}

        contract_right(s)

        assert s.loaded_end == 25
        assert all(idx <= 25 for idx in s.frames)
        assert all(idx <= 25 for idx in s.frame_signatures)

    def test_does_nothing_when_gap_too_small(self, make_state):
        s = make_state(loaded_end=99, active_end=97, base_step=5)
        original = s.loaded_end
        contract_right(s)
        assert s.loaded_end == original


# ---------------------------------------------------------------------------
# set_mark_in / set_mark_out
# ---------------------------------------------------------------------------

def _suggest_in(idx: int):
    def prepare(state: VideoState) -> None:
        state.suggestions.offer(idx, state.suggested_out)
    return prepare


def _suggest_out(idx: int):
    def prepare(state: VideoState) -> None:
        state.suggestions.offer(state.suggested_in, idx)
    return prepare


def _no_prep(state: VideoState) -> None:
    pass


def _speed(delta: float):
    def act(state: VideoState) -> None:
        change_speed(state, delta)
    return act


def _shift(direction: int):
    def act(state: VideoState) -> None:
        shift_active_range(state, direction)
    return act


# (label, _make_state kwargs, prepare, act) for every edit that changes the
# clip the user is cutting.  Each must set the dirty flag and autosave.
_EDITS_THAT_CHANGE_THE_CLIP = [
    ("set_mark_in", {"active_start": 5, "active_end": 50, "current": 20}, _no_prep, set_mark_in),
    ("set_mark_out", {"active_start": 5, "active_end": 50, "current": 30}, _no_prep, set_mark_out),
    ("accept_suggested_in", {"active_start": 10, "active_end": 30}, _suggest_in(12), accept_suggested_in),
    ("accept_suggested_out", {"active_start": 10, "active_end": 30}, _suggest_out(28), accept_suggested_out),
    ("shift_active_range", {"active_start": 10, "active_end": 20, "current": 14}, _no_prep, _shift(1)),
    ("cycle_loop_mode", {"loop_mode": "base-tip-base"}, _no_prep, cycle_loop_mode),
    ("toggle_wrap_mode", {"wrap_mode": "blue", "active_start": 10, "active_end": 20, "current": 25}, _no_prep, toggle_wrap_mode),
    ("contract_left", {"loaded_start": 10, "active_start": 20, "base_step": 5}, _no_prep, contract_left),
    ("contract_right", {"loaded_end": 99, "active_end": 70, "base_step": 5}, _no_prep, contract_right),
    ("extend_left", {"loaded_start": 20, "loaded_end": 60, "base_step": 5}, _no_prep, extend_left),
    ("extend_right", {"total_frames": 100, "loaded_end": 60, "base_step": 5}, _no_prep, extend_right),
    ("change_speed", {"speed": 1.0}, _no_prep, _speed(0.25)),
    ("move_current_left", {"loaded_start": 0, "loaded_end": 99, "current": 20}, _no_prep, move_current_left),
    ("move_current_right", {"loaded_start": 0, "loaded_end": 99, "current": 20}, _no_prep, move_current_right),
]

# The same operations asked to do something they refuse: nothing changes, so
# nothing is saved and the exit prompt stays away.
_EDITS_THAT_REFUSE = [
    ("set_mark_in past active_end", {"active_start": 5, "active_end": 50, "current": 55}, _no_prep, set_mark_in),
    ("set_mark_out before active_start", {"active_start": 20, "active_end": 50, "current": 10}, _no_prep, set_mark_out),
    ("accept_suggested_in at active_end", {"active_start": 10, "active_end": 30}, _suggest_in(30), accept_suggested_in),
    ("accept_suggested_out at active_start", {"active_start": 10, "active_end": 30}, _suggest_out(10), accept_suggested_out),
    ("shift_active_range out of bounds", {"active_start": 2, "active_end": 12, "current": 5}, _no_prep, _shift(-1)),
    ("contract_left with no room", {"loaded_start": 0, "active_start": 3, "base_step": 5}, _no_prep, contract_left),
    ("contract_right with no room", {"loaded_end": 99, "active_end": 97, "base_step": 5}, _no_prep, contract_right),
    ("change_speed already at the floor", {"speed": 0.25}, _no_prep, _speed(-0.25)),
]


class TestEditingMarksTheSessionDirty:
    """The flag that drives the exit prompt, and the autosave it triggers.

    Both used to be invisible: every editing test patched ``mark_dirty`` away
    to keep the session file off disk, so deleting the call from an edit
    operation left the whole suite green while in the app the user's marks
    stopped being saved and the exit dialog stopped appearing.
    """

    @pytest.mark.parametrize(
        "kwargs, prepare, act",
        [pytest.param(k, p, a, id=label) for label, k, p, a in _EDITS_THAT_CHANGE_THE_CLIP],
    )
    def test_an_edit_marks_the_session_dirty_and_saves_it(self, kwargs, prepare, act, make_state):
        s = make_state(**kwargs)
        prepare(s)
        before = s.render_rev
        act(s)
        assert s.dirty is True
        assert s.render_rev > before
        assert s.persist_session.calls == 1

    @pytest.mark.parametrize(
        "kwargs, prepare, act",
        [pytest.param(k, p, a, id=label) for label, k, p, a in _EDITS_THAT_REFUSE],
    )
    def test_a_refused_edit_leaves_the_session_clean(self, kwargs, prepare, act, make_state):
        s = make_state(**kwargs)
        prepare(s)
        act(s)
        assert s.dirty is False
        assert s.persist_session.calls == 0


class TestSetMarkIn:
    def test_advances_active_start_to_current(self, make_state):
        s = make_state(active_start=5, active_end=50, current=20)
        set_mark_in(s)
        assert s.active_start == 20

    def test_does_not_advance_past_active_end(self, make_state):
        s = make_state(active_start=5, active_end=50, current=55)
        original = s.active_start
        set_mark_in(s)
        # current > active_end, condition `current < active_end` is false → no change
        assert s.active_start == original


class TestSetMarkOut:
    def test_retreats_active_end_to_current(self, make_state):
        s = make_state(active_start=5, active_end=50, current=30)
        set_mark_out(s)
        assert s.active_end == 30

    def test_does_not_retreat_before_active_start(self, make_state):
        s = make_state(active_start=20, active_end=50, current=10)
        original = s.active_end
        set_mark_out(s)
        assert s.active_end == original


class TestAcceptSuggestedMarks:
    def test_accept_suggested_in_updates_active_start(self, make_state):
        s = make_state(active_start=10, active_end=30, loop_anchor=0.0)
        s.suggestions.offer(12, None)
        with patch("clipper.editing.update_loop_suggestions") as refresh_suggestions:
            accept_suggested_in(s)
        assert s.active_start == 12
        assert s.clip.anchor_in == 12
        assert s.loop.anchor > 0.0
        refresh_suggestions.assert_called_once_with(s)

    def test_accept_suggested_out_updates_active_end(self, make_state):
        s = make_state(active_start=10, active_end=30, loop_anchor=0.0)
        s.suggestions.offer(None, 28)
        with patch("clipper.editing.update_loop_suggestions") as refresh_suggestions:
            accept_suggested_out(s)
        assert s.active_end == 28
        assert s.clip.anchor_out == 28
        assert s.loop.anchor > 0.0
        refresh_suggestions.assert_called_once_with(s)

    def test_accept_suggested_in_ignores_invalid_candidate(self, make_state):
        s = make_state(active_start=10, active_end=30, loop_anchor=0.0)
        s.suggestions.offer(30, None)
        with patch("clipper.editing.update_loop_suggestions") as refresh_suggestions:
            accept_suggested_in(s)
        assert s.active_start == 10
        assert s.loop.anchor == 0.0
        refresh_suggestions.assert_not_called()

    def test_accept_suggested_out_ignores_invalid_candidate(self, make_state):
        s = make_state(active_start=10, active_end=30, loop_anchor=0.0)
        s.suggestions.offer(None, 10)
        with patch("clipper.editing.update_loop_suggestions") as refresh_suggestions:
            accept_suggested_out(s)
        assert s.active_end == 30
        assert s.loop.anchor == 0.0
        refresh_suggestions.assert_not_called()


class TestShiftActiveRange:
    def test_shift_right_reuses_old_out_as_new_in(self, make_state):
        s = make_state(active_start=10, active_end=20, current=14)
        shift_active_range(s, 1)
        assert s.active_start == 20
        assert s.active_end == 30
        assert s.current == 24

    def test_shift_left_reuses_old_in_as_new_out(self, make_state):
        s = make_state(active_start=20, active_end=30, current=26)
        shift_active_range(s, -1)
        assert s.active_start == 10
        assert s.active_end == 20
        assert s.current == 16

    def test_shift_right_expands_loaded_bounds_when_needed(self, make_state):
        s = make_state(loaded_start=0, loaded_end=24, active_start=10, active_end=20, current=12, total_frames=40)

        def fake_ensure_loaded(state: VideoState, want_start: int, want_end: int) -> None:
            state.window.widen_left_to(want_start)
            state.window.widen_right_to(want_end)

        with patch("clipper.editing.ensure_loaded", side_effect=fake_ensure_loaded):
            with patch("clipper.editing.update_loop_suggestions"):
                shift_active_range(s, 1)
        assert s.loaded_end == 35
        assert s.active_start == 20
        assert s.active_end == 30

    def test_shift_left_expands_loaded_bounds_when_needed(self, make_state):
        s = make_state(loaded_start=12, loaded_end=40, active_start=20, active_end=30, current=25, total_frames=60)

        def fake_ensure_loaded(state: VideoState, want_start: int, want_end: int) -> None:
            state.window.widen_left_to(want_start)
            state.window.widen_right_to(want_end)

        with patch("clipper.editing.ensure_loaded", side_effect=fake_ensure_loaded):
            with patch("clipper.editing.update_loop_suggestions"):
                shift_active_range(s, -1)
        assert s.loaded_start == 5
        assert s.active_start == 10
        assert s.active_end == 20

    def test_shift_right_preserves_existing_loaded_end_when_buffer_already_exists(self, make_state):
        s = make_state(loaded_start=0, loaded_end=40, active_start=10, active_end=20, current=14, base_step=5)
        with patch("clipper.editing.update_loop_suggestions"):
            shift_active_range(s, 1)
        assert s.loaded_end == 40
        assert s.active_end == 30

    def test_shift_left_preserves_existing_loaded_start_when_buffer_already_exists(self, make_state):
        s = make_state(loaded_start=0, loaded_end=40, active_start=20, active_end=30, current=24, base_step=5)
        with patch("clipper.editing.update_loop_suggestions"):
            shift_active_range(s, -1)
        assert s.loaded_start == 0
        assert s.active_start == 10

    def test_shift_pulls_the_cursor_back_inside_the_loaded_range(self, make_state):
        """The cursor moves with the range and can overshoot what is loaded."""
        s = make_state(total_frames=41, loaded_start=0, loaded_end=40,
                        active_start=0, active_end=20, current=39)
        shift_active_range(s, 1)
        assert (s.active_start, s.active_end) == (20, 40)
        assert s.current == 40

    def test_shift_does_nothing_if_it_would_leave_video_bounds(self, make_state):
        s = make_state(active_start=2, active_end=12, current=5, loop_anchor=0.0)
        original = (s.active_start, s.active_end, s.current)
        shift_active_range(s, -1)
        assert (s.active_start, s.active_end, s.current) == original
        assert s.loop.anchor == 0.0


class TestLoopSuggestions:
    def test_no_suggestions_for_untouched_initial_selection(self, make_state):
        s = make_state(active_start=10, active_end=40, initial_active_start=10, initial_active_end=40)
        update_loop_suggestions(s)
        assert s.suggested_in is None
        assert s.suggested_out is None

    def test_marked_in_suggests_neighbor_before_matching_return_frame(self, make_state):
        s = make_state(
            total_frames=80,
            loaded_start=0,
            loaded_end=79,
            active_start=10,
            active_end=60,
            current=10,
            initial_active_start=0,
            initial_active_end=60,
        )
        frames = {i: _pattern_frame(1000 + i) for i in range(80)}
        frames[10] = _pattern_frame(42)
        frames[12] = frames[10].copy()
        frames[50] = frames[10].copy()
        s.frames = frames

        update_loop_suggestions(s)

        assert s.suggested_in is None
        assert s.suggested_out == 49

    def test_when_both_marks_are_set_pair_can_nudge_to_better_neighboring_loop(self, make_state):
        s = make_state(
            total_frames=80,
            loaded_start=0,
            loaded_end=79,
            active_start=10,
            active_end=20,
            current=10,
            initial_active_start=0,
            initial_active_end=79,
        )
        frames = {i: _pattern_frame(2000 + i) for i in range(80)}
        frames[10] = _pattern_frame(11)
        frames[11] = _pattern_frame(12)
        frames[21] = frames[10].copy()
        frames[22] = frames[11].copy()
        s.frames = frames

        update_loop_suggestions(s)

        assert s.suggested_in == 11
        assert s.suggested_out == 21

    def test_refinement_stays_anchored_after_accepting_suggested_out(self, make_state):
        s = make_state(
            total_frames=80,
            loaded_start=0,
            loaded_end=79,
            active_start=10,
            active_end=20,
            current=10,
            initial_active_start=0,
            initial_active_end=79,
        )
        frames = {i: _pattern_frame(3000 + i) for i in range(80)}
        frames[10] = _pattern_frame(21)
        frames[11] = _pattern_frame(22)
        frames[12] = _pattern_frame(23)
        frames[21] = frames[10].copy()
        frames[22] = frames[11].copy()
        frames[23] = frames[12].copy()
        s.frames = frames
        s.suggestions.offer(None, 20)
        s.clip.anchor_in = 10
        s.clip.anchor_out = 20

        accept_suggested_out(s)
        update_loop_suggestions(s)

        first_pair = (s.suggested_in, s.suggested_out)

        s.clip.start, s.clip.end = first_pair
        update_loop_suggestions(s)

        assert (s.suggested_in, s.suggested_out) == first_pair

    @pytest.mark.parametrize("loop_mode, initial, turning_points, expected", [
        pytest.param("base-tip", (0, 60), [37], (None, 37), id="base-tip suggests the out point"),
        pytest.param("tip-base", (10, 79), [33], (33, None), id="tip-base suggests the in point"),
        pytest.param("base-tip", (0, 79), [35, 24], (24, 35), id="both marks moved"),
    ])
    def test_a_half_loop_mode_searches_for_turning_points_and_nothing_else(
        self, make_state, loop_mode, initial, turning_points, expected
    ):
        """base-tip and tip-base look for the turn, never for a duplicate frame
        and never for a better pair.

        This is the one rule here no frame fixture can show, because it is about
        which search runs rather than what it finds -- so it is the one test in
        this file that patches the searches by name. Three near-identical copies
        of it collapsed into this table.
        """
        s = make_state(
            total_frames=80, loaded_start=0, loaded_end=79,
            active_start=10, active_end=60,
            initial_active_start=initial[0], initial_active_end=initial[1],
            loop_mode=loop_mode,
        )

        with patch("clipper.loop_suggestions.best_turning_point_index",
                   side_effect=turning_points) as turning, \
             patch("clipper.loop_suggestions.best_duplicate_match_index") as duplicate, \
             patch("clipper.loop_suggestions.pair_transition_score") as pair_score:
            update_loop_suggestions(s)

        assert (s.suggested_in, s.suggested_out) == expected
        assert turning.call_count == len(turning_points)
        duplicate.assert_not_called()
        pair_score.assert_not_called()
