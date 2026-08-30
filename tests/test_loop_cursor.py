"""Tests for clipper.loop_cursor — where the loop preview is, and how fast.

The cursor is handed the clock rather than reading one, so none of this needs
a patched `time.monotonic`.
"""
from __future__ import annotations

from clipper.loop_cursor import LoopCursor

SEQUENCE = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
FPS = 10.0


class TestFrameWhileRunning:
    def test_the_frame_is_read_off_the_clock(self):
        cursor = LoopCursor(anchor=100.0)

        assert cursor.frame_in(SEQUENCE, FPS, now=100.45) == 14

    def test_it_wraps_round_the_end_of_the_sequence(self):
        cursor = LoopCursor(anchor=100.0)

        assert cursor.frame_in(SEQUENCE, FPS, now=101.25) == 12

    def test_speed_scales_how_far_the_clock_carries_it(self):
        cursor = LoopCursor(anchor=100.0, speed=2.0)

        assert cursor.frame_in(SEQUENCE, FPS, now=100.2) == 14

    def test_it_remembers_where_it_landed(self):
        cursor = LoopCursor(anchor=100.0)

        cursor.frame_in(SEQUENCE, FPS, now=100.45)

        assert (cursor.paused_pos, cursor.paused_idx) == (4, 14)


class TestFrameWhilePaused:
    def test_the_clock_moving_on_does_not_move_the_frame(self):
        cursor = LoopCursor(anchor=100.0, paused=True, paused_pos=4)

        first = cursor.frame_in(SEQUENCE, FPS, now=100.45)
        second = cursor.frame_in(SEQUENCE, FPS, now=180.0)

        assert (first, second) == (14, 14)

    def test_a_position_it_has_lost_is_recovered_from_the_frame(self):
        cursor = LoopCursor(anchor=100.0, paused=True, paused_idx=17)

        assert cursor.frame_in(SEQUENCE, FPS, now=100.45) == 17
        assert cursor.paused_pos == 7

    def test_a_frame_no_longer_in_the_sequence_falls_back_to_the_start(self):
        cursor = LoopCursor(anchor=100.0, paused=True, paused_idx=999)

        assert cursor.frame_in(SEQUENCE, FPS, now=100.45) == 10

    def test_a_position_past_the_end_of_a_shortened_sequence_is_pulled_back(self):
        cursor = LoopCursor(anchor=100.0, paused=True, paused_pos=40)

        assert cursor.frame_in(SEQUENCE, FPS, now=100.45) == 19


class TestASingleFrameSequence:
    def test_there_is_nowhere_to_be_but_the_one_frame(self):
        cursor = LoopCursor(anchor=100.0)

        assert cursor.frame_in([42], FPS, now=180.0) == 42
        assert (cursor.paused_pos, cursor.paused_idx) == (0, 42)


class TestTogglePause:
    def test_pausing_holds_the_frame_it_was_showing(self):
        cursor = LoopCursor(anchor=100.0)

        cursor.toggle_pause(SEQUENCE, FPS, now=100.45)

        assert cursor.paused is True
        assert cursor.frame_in(SEQUENCE, FPS, now=180.0) == 14

    def test_resuming_carries_on_from_the_frame_it_was_held_on(self):
        cursor = LoopCursor(anchor=100.0)
        cursor.toggle_pause(SEQUENCE, FPS, now=100.45)

        cursor.toggle_pause(SEQUENCE, FPS, now=100.45)

        assert cursor.paused is False
        assert cursor.frame_in(SEQUENCE, FPS, now=100.65) == 16

    def test_resuming_forgets_where_it_was_held(self):
        cursor = LoopCursor(anchor=100.0, paused=True, paused_pos=4, paused_idx=14)

        cursor.toggle_pause(SEQUENCE, FPS, now=100.45)

        assert (cursor.paused_pos, cursor.paused_idx) == (None, None)


class TestChangeSpeed:
    def test_a_nudge_moves_the_speed_by_a_quarter(self):
        cursor = LoopCursor(anchor=100.0, speed=1.0)

        assert cursor.change_speed(0.25, SEQUENCE, FPS, now=100.0) is True
        assert cursor.speed == 1.25

    def test_it_will_not_go_below_a_quarter_speed(self):
        cursor = LoopCursor(anchor=100.0, speed=0.25)

        assert cursor.change_speed(-0.25, SEQUENCE, FPS, now=100.0) is False
        assert cursor.speed == 0.25

    def test_it_will_not_go_above_double_speed(self):
        cursor = LoopCursor(anchor=100.0, speed=2.0)

        assert cursor.change_speed(0.25, SEQUENCE, FPS, now=100.0) is False
        assert cursor.speed == 2.0

    def test_a_paused_preview_keeps_the_frame_it_is_held_on(self):
        cursor = LoopCursor(anchor=100.0, speed=1.0, paused=True, paused_idx=14)

        cursor.change_speed(0.25, SEQUENCE, FPS, now=100.0)

        assert cursor.paused is True
        assert cursor.paused_idx == 14
        assert cursor.speed == 1.25

    def test_a_running_preview_does_not_jump_when_the_speed_changes(self):
        """Re-anchoring is what keeps the preview off a different frame.

        Within one frame, not on the same one: the anchor is `now` minus a
        division, so the elapsed time it implies can land a hair under a whole
        frame.  Left un-anchored this case shows frame 19 instead of 14.
        """
        cursor = LoopCursor(anchor=100.0, speed=1.0)
        assert cursor.frame_in(SEQUENCE, FPS, now=100.45) == 14

        cursor.change_speed(1.0, SEQUENCE, FPS, now=100.45)

        assert abs(cursor.frame_in(SEQUENCE, FPS, now=100.45) - 14) <= 1


class TestRestart:
    def test_restarting_puts_the_preview_back_at_the_first_frame(self):
        cursor = LoopCursor(anchor=100.0)

        cursor.restart_at(180.0)

        assert cursor.frame_in(SEQUENCE, FPS, now=180.0) == 10
