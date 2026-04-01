from __future__ import annotations

from .editing import (
    accept_suggested_in,
    accept_suggested_out,
    cycle_loop_mode,
    set_mark_in,
    set_mark_out,
    shift_active_range,
)
from .export import start_export_job
from .loaded_bounds import contract_left, contract_right, extend_left, extend_right
from .navigation import (
    move_current_left,
    move_current_right,
    toggle_wrap_mode,
)
from .paths import (
    ACCEPT_SUGGESTED_IN_KEYS,
    ACCEPT_SUGGESTED_OUT_KEYS,
    BOUNDS_CONTRACT_LEFT_KEYS,
    BOUNDS_CONTRACT_RIGHT_KEYS,
    BOUNDS_EXTEND_LEFT_KEYS,
    BOUNDS_EXTEND_RIGHT_KEYS,
    ENTER_KEYS,
    ESC_KEYS,
    LOOP_MODE_CYCLE_KEYS,
    MARK_IN_KEYS,
    MARK_OUT_KEYS,
    PLAY_PAUSE_KEYS,
    SHIFT_RANGE_LEFT_KEYS,
    SHIFT_RANGE_RIGHT_KEYS,
    SPEED_DOWN_KEYS,
    SPEED_UP_KEYS,
    WIN_LEFT_KEYS,
    WIN_RIGHT_KEYS,
    WRAP_TOGGLE_KEYS,
)
from .playback import change_speed, toggle_loop_pause
from .state import VideoState


def handle_key(state: VideoState, key: int) -> None:
    if key in WIN_LEFT_KEYS:
        move_current_left(state)
    elif key in WIN_RIGHT_KEYS:
        move_current_right(state)
    elif key in BOUNDS_EXTEND_LEFT_KEYS:
        extend_left(state)
    elif key in BOUNDS_CONTRACT_LEFT_KEYS:
        contract_left(state)
    elif key in BOUNDS_CONTRACT_RIGHT_KEYS:
        contract_right(state)
    elif key in BOUNDS_EXTEND_RIGHT_KEYS:
        extend_right(state)
    elif key in MARK_IN_KEYS:
        set_mark_in(state)
    elif key in MARK_OUT_KEYS:
        set_mark_out(state)
    elif key in ACCEPT_SUGGESTED_IN_KEYS:
        accept_suggested_in(state)
    elif key in ACCEPT_SUGGESTED_OUT_KEYS:
        accept_suggested_out(state)
    elif key in SHIFT_RANGE_LEFT_KEYS:
        shift_active_range(state, -1)
    elif key in SHIFT_RANGE_RIGHT_KEYS:
        shift_active_range(state, 1)
    elif key in WRAP_TOGGLE_KEYS:
        toggle_wrap_mode(state)
    elif key in LOOP_MODE_CYCLE_KEYS:
        cycle_loop_mode(state)
    elif key in PLAY_PAUSE_KEYS:
        toggle_loop_pause(state)
    elif key in SPEED_DOWN_KEYS:
        change_speed(state, -0.25)
    elif key in SPEED_UP_KEYS:
        change_speed(state, 0.25)
    elif key in ENTER_KEYS:
        start_export_job(state)
    elif key in ESC_KEYS and state.export_job and not state.export_job.dismissed:
        state.export_job.dismissed = True
