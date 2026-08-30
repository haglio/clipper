from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .loop_modes import (
    LOOP_MODE_BASE_TIP,
    LOOP_MODE_TIP_BASE,
    LOOP_MODE_TIP_BASE_TIP,
)

if TYPE_CHECKING:
    from .state import VideoState


def current_loop_frame_index(state: VideoState) -> int:
    return state.loop.frame_in(loop_preview_indices(state), state.fps, time.monotonic())


def loop_preview_indices(state: VideoState) -> list[int]:
    forward = list(range(state.active_start, state.active_end + 1))
    if not forward:
        return [state.active_start]
    if state.loop_mode == LOOP_MODE_TIP_BASE_TIP:
        shift = max(1, len(forward) // 2)
        return forward[shift:] + forward[:shift]
    if state.loop_mode == LOOP_MODE_BASE_TIP:
        return forward + forward[-2::-1]
    if state.loop_mode == LOOP_MODE_TIP_BASE:
        backward = list(reversed(forward))
        return backward[:-1] + forward
    return forward


def change_speed(state: VideoState, delta: float) -> None:
    moved = state.loop.change_speed(
        delta, loop_preview_indices(state), state.fps, time.monotonic()
    )
    if moved:
        state.mark_dirty()


def toggle_loop_pause(state: VideoState) -> None:
    state.loop.toggle_pause(loop_preview_indices(state), state.fps, time.monotonic())
    state.bump_render()
