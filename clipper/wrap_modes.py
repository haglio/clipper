"""Which range the cursor wraps within, and the one place that answers it.

The stored value is a color name because it is a key in the version-1 session
JSON that evolver enumerates and rewrites, and that format is unversioned -- so
the wire value stays `"blue"`/`"yellow"` and the constants carry the meaning the
color cannot.  (An enum was the other option and is not taken here: the loader
accepts whatever `wrap_mode` a session file holds and falls through to the
active range, so a closed type would start rejecting files it reads today.
That belongs with the family-wide sweep of bare-string mode sets, which can
settle the accepted set for all nine at once.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import VideoState

WRAP_OVER_LOADED = "blue"
WRAP_OVER_ACTIVE = "yellow"


def wrap_bounds(state: VideoState) -> tuple[int, int]:
    """The range the cursor may not leave, given the mode the state is in.

    Written out by hand at four sites before this, plus a fifth copy of the
    literal in the timeline widget.  A typo in any of them read as the active
    range and said nothing.
    """
    if state.wrap_mode == WRAP_OVER_LOADED:
        return state.loaded_start, state.loaded_end
    return state.active_start, state.active_end
