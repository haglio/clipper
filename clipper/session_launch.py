from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QDialog

from .create_session import create_session
from .gui.launcher_dialog import LauncherDialog
from .paths import LAST_SESSION_FILE, ensure_runtime_dirs
from .state import VideoState
from .state_factory import make_video_state
from .utils import parse_timestamp, read_json
from .vlc_prefill import detect_vlc_session_prefill


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
        vr=info.get("vr", False),
    )
    state = _load_state_from_session_file(session_path)
    LAST_SESSION_FILE.write_text(state.session_path, encoding="utf-8")
    return state


def launch_state() -> VideoState:
    ensure_runtime_dirs()
    last_session = LAST_SESSION_FILE.read_text(encoding="utf-8").strip() if LAST_SESSION_FILE.exists() else ""
    dialog = LauncherDialog(last_session=last_session)

    vlc_prefill = detect_vlc_session_prefill()
    if vlc_prefill:
        dialog.session_name_edit.setText(vlc_prefill.session_name)
        dialog.video_file_edit.setText(vlc_prefill.video_file)
        dialog.timestamp_edit.setText(vlc_prefill.timestamp)
        dialog.new_radio.setChecked(True)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        raise SystemExit(0)
    info = dialog.build_result()
    return build_state_from_launch_info(info)
