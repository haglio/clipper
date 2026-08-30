"""The in and out points of the clip being cut, and where they were set."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClipRange:
    """Owns `start < end`, and the anchors the suggestion search works around.

    Moving a mark also moves its anchor.  That pairing used to be written out
    at every one of the five sites that move a mark, and nothing said it was a
    rule -- so a sixth could have been added without it.
    """

    start: int
    end: int
    anchor_in: int | None = None
    anchor_out: int | None = None

    @property
    def span(self) -> int:
        """How far a shift travels: one clip length."""
        return self.end - self.start

    def mark_in(self, at: int) -> bool:
        """Put the in point at `at`, unless that would reach the out point."""
        if at >= self.end:
            return False
        self.start = at
        self.anchor_in = at
        return True

    def mark_out(self, at: int) -> bool:
        """Put the out point at `at`, unless that would reach the in point."""
        if at <= self.start:
            return False
        self.end = at
        self.anchor_out = at
        return True

    def shift(self, by: int) -> None:
        """Slide the whole clip, re-anchoring on where it lands."""
        self.start += by
        self.end += by
        self.anchor_in = self.start
        self.anchor_out = self.end
