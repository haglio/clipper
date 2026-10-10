"""The in and out points the app offers, and the selection it compares against.

The record only.  `loop_suggestions.py` holds the search that fills it and
`suggestion_search.py` the primitives that search runs on.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Suggestions:
    """Owns the offered pair, so "did it change?" is asked in one place."""

    initial_start: int | None = None
    initial_end: int | None = None
    suggested_in: int | None = None
    suggested_out: int | None = None

    def moved(self, start: int, end: int) -> tuple[bool, bool]:
        """Whether each mark has left the selection the session opened with.

        A session with no opening selection recorded has nothing to have moved
        from, so neither mark counts as moved and no search runs.
        """
        return (
            self.initial_start is not None and start != self.initial_start,
            self.initial_end is not None and end != self.initial_end,
        )

    def offer(self, suggested_in: int | None, suggested_out: int | None) -> bool:
        """Take a new pair; returns whether it differs from the one held."""
        if (suggested_in, suggested_out) == (self.suggested_in, self.suggested_out):
            return False
        self.suggested_in = suggested_in
        self.suggested_out = suggested_out
        return True
