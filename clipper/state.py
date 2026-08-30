from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from .frame_window import FrameWindow
from .loop_modes import LOOP_MODE_BASE_TIP_BASE
from .session_persistence import (
    autosave_session as persist_session_state,
    current_payload as build_current_payload,
)


@dataclass
class ExportJob:
    stage: str = ""
    clip_progress: float = 0.0
    fix_progress: float = 0.0
    audio_progress: float = 0.0
    procs: list[subprocess.Popen[str]] = field(default_factory=list)


@dataclass
class VideoState:
    cap: cv2.VideoCapture
    path: str
    fps: float
    window: FrameWindow
    active_start: int
    active_end: int
    frames: dict[int, np.ndarray]
    loop_anchor: float
    session_name: str
    session_path: str
    original_session_payload: dict[str, Any]
    loop_mode: str = LOOP_MODE_BASE_TIP_BASE
    wrap_mode: str = "blue"
    skip_postprocess: bool = False
    speed: float = 1.0
    vr: bool = False
    session_warning: str = ""
    dirty: bool = False
    protect_existing_save_data: bool = False
    last_saved_payload: dict[str, Any] | None = None
    render_rev: int = 0
    loop_paused: bool = False
    paused_loop_idx: int | None = None
    paused_loop_pos: int | None = None
    initial_active_start: int | None = None
    initial_active_end: int | None = None
    suggested_in: int | None = None
    suggested_out: int | None = None
    suggestion_anchor_in: int | None = None
    suggestion_anchor_out: int | None = None
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

    @property
    def should_prompt_on_exit(self) -> bool:
        return self.dirty and self.protect_existing_save_data

    def clamp_current(self) -> None:
        low = self.loaded_start if self.wrap_mode == "blue" else self.active_start
        high = self.loaded_end if self.wrap_mode == "blue" else self.active_end
        self.window.hold_within(low, high)

    def reset_loop_anchor(self) -> None:
        self.loop_anchor = time.monotonic()

    def mark_dirty(self) -> None:
        self.dirty = True
        self.render_rev += 1
        self.autosave_session()

    def current_payload(self) -> dict[str, Any]:
        return build_current_payload(self)

    def autosave_session(self) -> None:
        self.persist_session(self)
