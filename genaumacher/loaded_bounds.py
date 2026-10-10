from __future__ import annotations

from typing import TYPE_CHECKING

from .frame_store import ensure_loaded, prune_loaded_caches
from .loop_suggestions import update_loop_suggestions

if TYPE_CHECKING:
    from .state import VideoState


def contract_left(state: VideoState) -> None:
    if state.window.contract_left(state.active_start):
        prune_loaded_caches(state)
        update_loop_suggestions(state)
        state.mark_dirty()


def extend_left(state: VideoState) -> None:
    before = state.loaded_start
    ensure_loaded(state, state.window.step_out_left(), state.loaded_end)
    if state.loaded_start == before:
        return  # at the start of the video: nothing moved, nothing to save
    update_loop_suggestions(state)
    state.mark_dirty()


def contract_right(state: VideoState) -> None:
    if state.window.contract_right(state.active_end):
        prune_loaded_caches(state)
        update_loop_suggestions(state)
        state.mark_dirty()


def extend_right(state: VideoState) -> None:
    before = state.loaded_end
    # The edge is the last frame `ensure_loaded` got: the loader itself gets
    # past a damaged read, so nothing here has to claim frames it never saw.
    ensure_loaded(state, state.loaded_start, state.window.step_out_right())
    if state.loaded_end == before:
        return  # the end of the video, or of what decodes: nothing to save
    update_loop_suggestions(state)
    state.mark_dirty()
