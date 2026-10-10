"""How an exported clip's frames are laid out to loop, as the session file spells it."""
from __future__ import annotations

from enum import StrEnum


class LoopMode(StrEnum):
    BASE_TIP_BASE = "base-tip-base"
    TIP_BASE_TIP = "tip-base-tip"
    BASE_TIP = "base-tip"
    TIP_BASE = "tip-base"


# The order the loop button cycles them in.
LOOP_MODES = tuple(LoopMode)


def read_loop_mode(raw: object) -> LoopMode:
    """The entry *raw* names, or the one a new session starts in for a word this
    build does not know -- a session file from another build must still open."""
    try:
        return LoopMode(raw)
    except ValueError:
        return LoopMode.BASE_TIP_BASE
