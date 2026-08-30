"""The stretch of the video that is loaded, and where the cursor sits in it."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FrameWindow:
    """Owns `loaded_start <= loaded_end` and the cursor that roams inside it."""

    total_frames: int
    loaded_start: int
    loaded_end: int
    current: int
    base_step: int

    @property
    def count(self) -> int:
        return self.loaded_end - self.loaded_start + 1

    def hold_within(self, low: int, high: int) -> None:
        """Pull the cursor back inside `[low, high]`."""
        self.current = max(low, min(high, self.current))

    def contract_left(self, active_start: int) -> bool:
        """Drop one step off the left, unless that would eat the active range.

        Returns whether the window moved, so the caller knows whether there is
        anything to prune, re-suggest or save.
        """
        if active_start - self.loaded_start < self.base_step:
            return False
        self.loaded_start += self.base_step
        self.current = max(self.current, self.loaded_start)
        return True

    def contract_right(self, active_end: int) -> bool:
        """Drop one step off the right, unless that would eat the active range."""
        if self.loaded_end - active_end < self.base_step:
            return False
        self.loaded_end -= self.base_step
        self.current = min(self.current, self.loaded_end)
        return True

    def step_out_left(self) -> int:
        """Where a step further left would put `loaded_start`."""
        return max(0, self.loaded_start - self.base_step)

    def step_out_right(self) -> int:
        """Where a step further right would put `loaded_end`."""
        return min(self.total_frames - 1, self.loaded_end + self.base_step)

    def widen_left_to(self, start: int) -> None:
        """Take in `start`, once its frames are loaded.  Never narrows."""
        self.loaded_start = min(self.loaded_start, start)

    def widen_right_to(self, end: int) -> None:
        """Take in `end`, once its frames are loaded.  Never narrows."""
        self.loaded_end = max(self.loaded_end, end)

    def reach_right_to(self, end: int) -> None:
        """Put the right edge on `end`, decoded or not.

        Unlike `widen_right_to` this takes the caller's word for it, which is
        what `extend_right` has always done: it asks for a step out and then
        claims it whether or not every frame arrived.  On a file the decoder
        gives up on early that leaves the window spanning frames nothing
        produced, and `safe_frame` raises for them.  Kept because it is the
        behaviour the app has; see the item-40 changelog note.
        """
        self.loaded_end = end

    def step_cursor_back(self, low: int, high: int) -> None:
        """One frame back, wrapping to `high` at `low`."""
        self.current = high if self.current <= low else self.current - 1

    def step_cursor_forward(self, low: int, high: int) -> None:
        """One frame on, wrapping to `low` at `high`."""
        self.current = low if self.current >= high else self.current + 1

    def carry_cursor(self, shift: int) -> None:
        """Move the cursor by the same amount the active range just moved."""
        self.current += shift

    def jump_to(self, idx: int) -> None:
        """Put the cursor on `idx` -- what a click on the timeline asks for."""
        self.current = idx
