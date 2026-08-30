from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import VideoState


def toggle_wrap_mode(state: VideoState) -> None:
    state.wrap_mode = "yellow" if state.wrap_mode == "blue" else "blue"
    if state.wrap_mode == "yellow":
        state.window.hold_within(state.active_start, state.active_end)
    state.mark_dirty()


def move_current_left(state: VideoState) -> None:
    low = state.loaded_start if state.wrap_mode == "blue" else state.active_start
    high = state.loaded_end if state.wrap_mode == "blue" else state.active_end
    state.window.step_cursor_back(low, high)
    state.mark_dirty()


def move_current_right(state: VideoState) -> None:
    low = state.loaded_start if state.wrap_mode == "blue" else state.active_start
    high = state.loaded_end if state.wrap_mode == "blue" else state.active_end
    state.window.step_cursor_forward(low, high)
    state.mark_dirty()
