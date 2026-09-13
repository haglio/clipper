from __future__ import annotations

from typing import TYPE_CHECKING

from .wrap_modes import WrapMode, wrap_bounds

if TYPE_CHECKING:
    from .state import VideoState


def toggle_wrap_mode(state: VideoState) -> None:
    state.wrap_mode = (
        WrapMode.OVER_ACTIVE if state.wrap_mode is WrapMode.OVER_LOADED else WrapMode.OVER_LOADED
    )
    if state.wrap_mode is WrapMode.OVER_ACTIVE:
        state.window.hold_within(*wrap_bounds(state))
    state.mark_dirty()


def move_current_left(state: VideoState) -> None:
    state.window.step_cursor_back(*wrap_bounds(state))
    state.mark_dirty()


def move_current_right(state: VideoState) -> None:
    state.window.step_cursor_forward(*wrap_bounds(state))
    state.mark_dirty()
