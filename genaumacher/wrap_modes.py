"""Which range the cursor wraps within, and the one place that answers it.

The two words are colors because they are values in the version-1 session JSON
that evolver enumerates and rewrites, and that format is unversioned -- so the
wire word stays `"blue"`/`"yellow"` and the entries carry the meaning the color
cannot.  A word this build does not know reads as the range a new session
wraps within, rather than being rejected or falling through to the active one.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import VideoState


class WrapMode(StrEnum):
    OVER_LOADED = "blue"
    OVER_ACTIVE = "yellow"


def read_wrap_mode(raw: object) -> WrapMode:
    try:
        return WrapMode(raw)
    except ValueError:
        return WrapMode.OVER_LOADED


def wrap_bounds(state: VideoState) -> tuple[int, int]:
    """The range the cursor may not leave, given the mode the state is in.

    Written out by hand at four sites before this, plus a fifth copy of the
    literal in the timeline widget.  A typo in any of them read as the active
    range and said nothing.
    """
    if state.wrap_mode is WrapMode.OVER_LOADED:
        return state.loaded_start, state.loaded_end
    return state.active_start, state.active_end
