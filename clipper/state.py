from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from .clip_range import ClipRange
from .frame_window import FrameWindow
from .loop_cursor import LoopCursor
from .loop_modes import LOOP_MODE_BASE_TIP_BASE
from .session_persistence import (
    autosave_session as persist_session_state,
)
from .session_persistence import (
    current_payload as build_current_payload,
)
from .suggestions import Suggestions
from .wrap_modes import WRAP_OVER_LOADED, wrap_bounds


@dataclass
class VideoState:
    cap: cv2.VideoCapture
    path: str
    fps: float
    window: FrameWindow
    clip: ClipRange
    frames: dict[int, np.ndarray]
    loop: LoopCursor
    suggestions: Suggestions
    session_name: str
    session_path: str
    original_session_payload: dict[str, Any]
    loop_mode: str = LOOP_MODE_BASE_TIP_BASE
    wrap_mode: str = WRAP_OVER_LOADED
    skip_postprocess: bool = False
    vr: bool = False
    session_warning: str = ""
    dirty: bool = False
    protect_existing_save_data: bool = False
    last_saved_payload: dict[str, Any] | None = None
    render_rev: int = 0
    frame_signatures: dict[int, np.ndarray] = field(default_factory=dict)
    # The disk write mark_dirty triggers, held as a collaborator so a caller
    # that only wants the flag can supply one that writes nothing.  Editing
    # tests used to reach that by patching mark_dirty itself, which also
    # patched away the flag and the render bump the edit operations exist to
    # set -- so the call could be deleted from three of them with the whole
    # suite green.
    persist_session: Callable[[VideoState], None] = field(
        default=persist_session_state, repr=False
    )

    # The frame window's five fields are session-JSON keys, so they are readable
    # here under the names the payload builder writes -- but only readable.  A
    # module that wants one changed asks the window for the change it wants;
    # that is what stops `loaded_start <= current <= loaded_end` being
    # re-established by hand at every call site.

    @property
    def total_frames(self) -> int:
        return self.window.total_frames

    @property
    def loaded_start(self) -> int:
        return self.window.loaded_start

    @property
    def loaded_end(self) -> int:
        return self.window.loaded_end

    @property
    def current(self) -> int:
        return self.window.current

    @property
    def base_step(self) -> int:
        return self.window.base_step

    @property
    def loaded_count(self) -> int:
        return self.window.count

    # The clip's two ends are session-JSON keys as well.  Its two anchors are
    # not, and nothing outside `loop_suggestions` reads them, so they stay on
    # the range rather than getting a reader here that only a test would use.

    @property
    def active_start(self) -> int:
        return self.clip.start

    @property
    def active_end(self) -> int:
        return self.clip.end

    # The offered pair is drawn on the timeline and read by the two accept
    # operations; the opening selection it is compared against is nobody's
    # business but the search's.

    @property
    def suggested_in(self) -> int | None:
        return self.suggestions.suggested_in

    @property
    def suggested_out(self) -> int | None:
        return self.suggestions.suggested_out

    # The loop cursor's, likewise.  `speed` is a session-JSON key; the other
    # two are what the tick reads to draw the transport.  The anchor and the
    # paused frame are not here: nothing outside the cursor reads either, and a
    # reader that only a test has is how the last four dead surfaces got in.

    @property
    def speed(self) -> float:
        return self.loop.speed

    @property
    def loop_paused(self) -> bool:
        return self.loop.paused

    @property
    def paused_loop_pos(self) -> int | None:
        return self.loop.paused_pos

    @property
    def should_prompt_on_exit(self) -> bool:
        return self.dirty and self.protect_existing_save_data

    def clamp_current(self) -> None:
        self.window.hold_within(*wrap_bounds(self))

    def reset_loop_anchor(self) -> None:
        self.loop.restart_at(time.monotonic())

    def bump_render(self) -> None:
        """Say the picture changed.

        Nothing reads the count -- the 60 Hz tick repaints regardless -- so it
        is the edit tables' cheapest observable rather than a repaint gate
        (`backlog.md` §4.3).  One method, so the five sites that used to reach
        in and increment the field cannot disagree about what a bump is.
        """
        self.render_rev += 1

    def mark_dirty(self) -> None:
        self.dirty = True
        self.bump_render()
        self.autosave_session()

    def current_payload(self) -> dict[str, Any]:
        return build_current_payload(self)

    def autosave_session(self) -> None:
        self.persist_session(self)
