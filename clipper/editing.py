from __future__ import annotations

from typing import TYPE_CHECKING

from .frame_store import ensure_loaded
from .loop_suggestions import update_loop_suggestions
from .loop_modes import LOOP_MODES

if TYPE_CHECKING:
    from .state import VideoState


def _mark_moved(state: VideoState) -> None:
    """What every accepted mark does after the clip range has taken it."""
    state.reset_loop_anchor()
    update_loop_suggestions(state)
    state.mark_dirty()


def set_mark_in(state: VideoState) -> None:
    if state.clip.mark_in(state.current):
        _mark_moved(state)


def set_mark_out(state: VideoState) -> None:
    if state.clip.mark_out(state.current):
        _mark_moved(state)


def accept_suggested_in(state: VideoState) -> None:
    suggested = state.suggested_in
    if suggested is not None and state.clip.mark_in(suggested):
        _mark_moved(state)


def accept_suggested_out(state: VideoState) -> None:
    suggested = state.suggested_out
    if suggested is not None and state.clip.mark_out(suggested):
        _mark_moved(state)


def shift_active_range(state: VideoState, direction: int) -> None:
    if direction == 0:
        return
    shift = state.clip.span * (1 if direction > 0 else -1)
    if shift == 0:
        return

    new_start = state.clip.start + shift
    new_end = state.clip.end + shift
    if new_start < 0 or new_end >= state.total_frames:
        return

    want_start = new_start
    want_end = new_end
    if direction > 0:
        want_end = min(state.total_frames - 1, new_end + state.base_step)
    else:
        want_start = max(0, new_start - state.base_step)

    ensure_loaded(state, want_start, want_end)
    state.clip.shift(shift)
    state.window.carry_cursor(shift)
    state.clamp_current()
    _mark_moved(state)


def cycle_loop_mode(state: VideoState, step: int = 1) -> None:
    current_idx = LOOP_MODES.index(state.loop_mode) if state.loop_mode in LOOP_MODES else 0
    state.loop_mode = LOOP_MODES[(current_idx + step) % len(LOOP_MODES)]
    state.mark_dirty()
