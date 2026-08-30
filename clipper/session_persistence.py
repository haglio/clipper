from __future__ import annotations

from pathlib import Path

from .paths import LAST_SESSION_FILE
from .utils import safe_atomic_write_json


SESSION_FORMAT_VERSION = 1


def session_payload(
    *,
    session_name: str,
    video_path: str,
    fps: float,
    total_frames: int,
    loaded_start: int,
    loaded_end: int,
    active_start: int,
    active_end: int,
    current: int,
    seconds_per_step: float,
    loop_mode: str,
    wrap_mode: str,
    speed: float,
    vr: bool,
) -> dict:
    """The on-disk session format, in one place.

    It was three hand-written dict literals -- one that creates a session, one
    that rewrites it on every edit, and one in the state factory that had
    already drifted (fourteen keys, no `vr`).  Evolver enumerates this
    directory and rewrites `video_path` in it, so the key set and its order are
    a contract with another repo, not an implementation detail.
    """
    return {
        "version": SESSION_FORMAT_VERSION,
        "session_name": session_name,
        "video_path": video_path,
        "fps": fps,
        "total_frames": total_frames,
        "loaded_start": loaded_start,
        "loaded_end": loaded_end,
        "active_start": active_start,
        "active_end": active_end,
        "current": current,
        "seconds_per_step": seconds_per_step,
        "loop_mode": loop_mode,
        "wrap_mode": wrap_mode,
        "speed": speed,
        "vr": vr,
    }


def current_payload(state) -> dict:
    """The session as it stands now, ready to be written back."""
    return session_payload(
        session_name=state.session_name,
        video_path=state.path,
        fps=state.fps,
        total_frames=state.total_frames,
        loaded_start=state.loaded_start,
        loaded_end=state.loaded_end,
        active_start=state.active_start,
        active_end=state.active_end,
        current=state.current,
        seconds_per_step=state.base_step / state.fps,
        loop_mode=state.loop_mode,
        wrap_mode=state.wrap_mode,
        speed=state.speed,
        vr=state.vr,
    )


def autosave_session(state) -> None:
    payload = current_payload(state)
    ok, detail = safe_atomic_write_json(Path(state.session_path), payload)
    if ok:
        state.session_warning = ""
        state.last_saved_payload = payload
        try:
            LAST_SESSION_FILE.write_text(state.session_path, encoding="utf-8")
        except Exception:
            pass
    else:
        state.session_warning = f"Autosave failed: {detail}"
