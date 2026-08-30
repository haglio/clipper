from __future__ import annotations

import time
from typing import Any

import cv2

from .clip_range import ClipRange
from .frame_store import load_range
from .frame_window import FrameWindow
from .loop_cursor import LoopCursor
from .loop_suggestions import update_loop_suggestions
from .loop_modes import LOOP_MODE_BASE_TIP_BASE, LOOP_MODES
from .paths import SESSIONS_DIR, sanitize_name
from .state import VideoState
from .suggestions import Suggestions
from .wrap_modes import WRAP_OVER_LOADED


def _normalized_loop_mode(loop_mode: str) -> str:
    return loop_mode if loop_mode in LOOP_MODES else LOOP_MODE_BASE_TIP_BASE


def _normalized_speed(speed: float) -> float:
    return max(0.25, min(2.0, round(speed * 4) / 4))


def load_video_state(payload: dict[str, Any], session_name: str) -> VideoState:
    """Open the video a saved session names, and rebuild the state from it.

    `session_name` is the caller's fallback -- the session file's own stem --
    for a payload that does not carry one.

    This was `make_video_state`, six parameters branching on whether a payload
    was supplied.  Nothing outside the tests reached the other branch: a new
    session is `create_session` writing the file and this reading it back, so
    the only production caller has always had a payload.  That branch was also
    the fourth copy of the version-1 payload literal, and the drifted one -- it
    omitted `vr`, so the two representations of "a new session" disagreed.
    """
    video_path = payload["video_path"]
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(round(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    if not fps or fps <= 0:
        raise RuntimeError("Invalid FPS metadata")
    if total_frames <= 0:
        raise RuntimeError("Invalid frame count metadata")

    loaded_start = int(payload["loaded_start"])
    loaded_end = int(payload["loaded_end"])
    active_start = int(payload["active_start"])
    active_end = int(payload["active_end"])
    current = int(payload.get("current", active_start))
    loop_mode = _normalized_loop_mode(str(payload.get("loop_mode", LOOP_MODE_BASE_TIP_BASE)))
    wrap_mode = payload.get("wrap_mode", WRAP_OVER_LOADED)
    speed = _normalized_speed(float(payload.get("speed", 1.0)))
    vr = bool(payload.get("vr", False))
    session_name = payload.get("session_name", session_name)

    frames = load_range(cap, loaded_start, loaded_end)
    if not frames:
        raise RuntimeError("No frames were extracted for the requested/session interval")
    state = VideoState(
        cap=cap,
        path=video_path,
        fps=fps,
        window=FrameWindow(
            total_frames=total_frames,
            loaded_start=loaded_start,
            loaded_end=max(frames.keys()),
            current=current,
            base_step=max(1, int(round(fps))),
        ),
        clip=ClipRange(
            start=active_start,
            end=active_end,
            anchor_in=active_start,
            anchor_out=active_end,
        ),
        frames=frames,
        loop=LoopCursor(anchor=time.monotonic(), speed=speed),
        suggestions=Suggestions(initial_start=active_start, initial_end=active_end),
        session_name=session_name,
        session_path=str(SESSIONS_DIR / f"{sanitize_name(session_name)}.json"),
        original_session_payload=dict(payload),
        loop_mode=loop_mode,
        wrap_mode=wrap_mode,
        vr=vr,
    )
    state.clamp_current()
    state.last_saved_payload = state.current_payload()
    update_loop_suggestions(state)
    return state
