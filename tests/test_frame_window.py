"""Tests for clipper.frame_window — the loaded stretch and the cursor in it."""
from __future__ import annotations

from clipper.frame_window import FrameWindow


def _window(**overrides) -> FrameWindow:
    kwargs = dict(total_frames=100, loaded_start=10, loaded_end=60,
                  current=30, base_step=5)
    kwargs.update(overrides)
    return FrameWindow(**kwargs)


class TestCount:
    def test_it_counts_both_ends_of_the_loaded_stretch(self):
        assert _window(loaded_start=0, loaded_end=49).count == 50

    def test_a_single_loaded_frame_counts_as_one(self):
        assert _window(loaded_start=5, loaded_end=5).count == 1


class TestHoldWithin:
    """The cursor is pulled back into whatever range it is told to stay in."""

    def test_a_cursor_below_the_range_is_pulled_up_to_the_floor(self):
        window = _window(current=5)

        window.hold_within(10, 60)

        assert window.current == 10

    def test_a_cursor_above_the_range_is_pulled_down_to_the_ceiling(self):
        window = _window(current=99)

        window.hold_within(10, 60)

        assert window.current == 60

    def test_a_cursor_already_inside_it_does_not_move(self):
        window = _window(current=30)

        window.hold_within(10, 60)

        assert window.current == 30


class TestContractLeft:
    """One step off the left, never eating into the active range."""

    def test_it_takes_one_step_off_the_left(self):
        window = _window(loaded_start=10, base_step=5)

        assert window.contract_left(active_start=20) is True
        assert window.loaded_start == 15

    def test_it_refuses_when_a_step_would_reach_the_active_range(self):
        window = _window(loaded_start=0, base_step=5)

        assert window.contract_left(active_start=3) is False
        assert window.loaded_start == 0

    def test_a_step_that_lands_exactly_on_the_active_start_is_allowed(self):
        window = _window(loaded_start=10, base_step=5)

        assert window.contract_left(active_start=15) is True
        assert window.loaded_start == 15

    def test_it_drags_a_stranded_cursor_along(self):
        window = _window(loaded_start=10, current=12, base_step=5)

        window.contract_left(active_start=20)

        assert window.current == 15


class TestContractRight:
    """The mirror of the left contraction."""

    def test_it_takes_one_step_off_the_right(self):
        window = _window(loaded_end=99, base_step=5)

        assert window.contract_right(active_end=70) is True
        assert window.loaded_end == 94

    def test_it_refuses_when_a_step_would_reach_the_active_range(self):
        window = _window(loaded_end=99, base_step=5)

        assert window.contract_right(active_end=97) is False
        assert window.loaded_end == 99

    def test_it_drags_a_stranded_cursor_along(self):
        window = _window(loaded_end=99, current=98, base_step=5)

        window.contract_right(active_end=70)

        assert window.current == 94


class TestStepOut:
    """Where one step further out would land, stopped by the video's own ends."""

    def test_a_step_out_to_the_left_is_one_base_step(self):
        assert _window(loaded_start=20, base_step=5).step_out_left() == 15

    def test_a_step_out_to_the_left_stops_at_the_first_frame(self):
        assert _window(loaded_start=2, base_step=5).step_out_left() == 0

    def test_a_step_out_to_the_right_is_one_base_step(self):
        assert _window(loaded_end=60, base_step=5, total_frames=100).step_out_right() == 65

    def test_a_step_out_to_the_right_stops_at_the_last_frame(self):
        assert _window(loaded_end=97, base_step=5, total_frames=100).step_out_right() == 99


class TestWiden:
    """The two writes the frame loader makes once the frames are actually in.

    They only ever widen: a loader that came back with less than it was asked
    for cannot narrow the window out from under the cursor.
    """

    def test_it_moves_the_left_edge_out(self):
        window = _window(loaded_start=20)

        window.widen_left_to(15)

        assert window.loaded_start == 15

    def test_a_left_edge_already_further_out_stands(self):
        window = _window(loaded_start=20)

        window.widen_left_to(25)

        assert window.loaded_start == 20

    def test_it_moves_the_right_edge_out(self):
        window = _window(loaded_end=60)

        window.widen_right_to(65)

        assert window.loaded_end == 65

    def test_a_right_edge_already_further_out_stands(self):
        window = _window(loaded_end=60)

        window.widen_right_to(55)

        assert window.loaded_end == 60


class TestStepCursor:
    """One frame at a time, wrapping round the ends of the range it is given.

    The range is not always the loaded one -- in the active wrap mode the
    cursor is confined to the clip -- so both ends are passed in.
    """

    def test_stepping_back_moves_one_frame(self):
        window = _window(current=30)

        window.step_cursor_back(10, 60)

        assert window.current == 29

    def test_stepping_back_off_the_floor_wraps_to_the_ceiling(self):
        window = _window(current=10)

        window.step_cursor_back(10, 60)

        assert window.current == 60

    def test_stepping_forward_moves_one_frame(self):
        window = _window(current=30)

        window.step_cursor_forward(10, 60)

        assert window.current == 31

    def test_stepping_forward_off_the_ceiling_wraps_to_the_floor(self):
        window = _window(current=60)

        window.step_cursor_forward(10, 60)

        assert window.current == 10


class TestCarryAndJump:
    def test_carrying_moves_the_cursor_with_the_range_it_sits_in(self):
        window = _window(current=30)

        window.carry_cursor(10)

        assert window.current == 40

    def test_jumping_puts_the_cursor_where_it_was_asked(self):
        window = _window(current=30)

        window.jump_to(47)

        assert window.current == 47
