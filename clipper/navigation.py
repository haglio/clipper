from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import VideoState


def toggle_wrap_mode(state: VideoState) -> None:
    state.wrap_mode = "yellow" if state.wrap_mode == "blue" else "blue"
    if state.wrap_mode == "yellow":
        state.current = max(state.active_start, min(state.active_end, state.current))
    state.mark_dirty()


def move_current_left(state: VideoState) -> None:
    low = state.loaded_start if state.wrap_mode == "blue" else state.active_start
    high = state.loaded_end if state.wrap_mode == "blue" else state.active_end
    if state.current <= low:
        state.current = high
    else:
        state.current -= 1
    state.render_rev += 1


def move_current_right(state: VideoState) -> None:
    low = state.loaded_start if state.wrap_mode == "blue" else state.active_start
    high = state.loaded_end if state.wrap_mode == "blue" else state.active_end
    if state.current >= high:
        state.current = low
    else:
        state.current += 1
    state.render_rev += 1
