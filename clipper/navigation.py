from __future__ import annotations

from typing import TYPE_CHECKING

from .wrap_modes import WRAP_OVER_ACTIVE, WRAP_OVER_LOADED, wrap_bounds

if TYPE_CHECKING:
    from .state import VideoState


def toggle_wrap_mode(state: VideoState) -> None:
    state.wrap_mode = (
        WRAP_OVER_ACTIVE if state.wrap_mode == WRAP_OVER_LOADED else WRAP_OVER_LOADED
    )
    if state.wrap_mode == WRAP_OVER_ACTIVE:
        state.window.hold_within(*wrap_bounds(state))
    state.mark_dirty()


def move_current_left(state: VideoState) -> None:
    state.window.step_cursor_back(*wrap_bounds(state))
    state.mark_dirty()


def move_current_right(state: VideoState) -> None:
    state.window.step_cursor_forward(*wrap_bounds(state))
    state.mark_dirty()
