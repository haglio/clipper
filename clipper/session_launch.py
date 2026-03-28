from __future__ import annotations

from pathlib import Path

from .create_session import create_session
from .launcher import launcher_dialog
from .paths import LAST_SESSION_FILE, ensure_runtime_dirs
from .state import VideoState
from .state_factory import make_video_state
from .utils import parse_timestamp, read_json


def _load_state_from_session_file(session_path: Path) -> VideoState:
    payload = read_json(session_path)
    state = make_video_state(
        payload["video_path"],
        payload.get("session_name", session_path.stem),
        0.0,
        5.0,
        payload_override=payload,
    )
    state.session_path = str(session_path)
    state.original_session_payload = dict(payload)
    state.protect_existing_save_data = True
    return state


def build_state_from_launch_info(info: dict) -> VideoState:
    if info["mode"] == "load":
        session_path = Path(info["session_json"])
        state = _load_state_from_session_file(session_path)
        LAST_SESSION_FILE.write_text(state.session_path, encoding="utf-8")
        return state

    session_path = create_session(
        info["video_file"],
        parse_timestamp(info["timestamp"]),
        session_name=info["session_name"],
        seconds=info["seconds"],
        loop_mode=info.get("loop_mode", "base-tip-base"),
    )
    state = _load_state_from_session_file(session_path)
    LAST_SESSION_FILE.write_text(state.session_path, encoding="utf-8")
    return state


def launch_state() -> VideoState:
    ensure_runtime_dirs()
    info = launcher_dialog()
    if not info.get("ok"):
        raise SystemExit(0)
    return build_state_from_launch_info(info)
