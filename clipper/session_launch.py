from __future__ import annotations

import time
from pathlib import Path

import cv2

from PyQt6.QtWidgets import QDialog

from .clip_range import ClipRange
from .create_session import _ffprobe_video_metadata, create_session
from .frame_window import FrameWindow
from .gui.launcher_dialog import LauncherDialog
from .loop_cursor import LoopCursor
from .paths import LAST_SESSION_FILE, SESSIONS_DIR, ensure_runtime_dirs
from .state import VideoState
from .state_factory import load_video_state
from .suggestions import Suggestions
from .utils import parse_timestamp, read_json, sanitize_name
from .nau_prefill import detect_nau_session_prefill


def _load_state_from_session_file(session_path: Path) -> VideoState:
    payload = read_json(session_path)
    state = load_video_state(payload, session_path.stem)
    state.session_path = str(session_path)
    state.protect_existing_save_data = True
    return state


def build_clip_whole_state(video_file: str) -> VideoState:
    """Build a lightweight VideoState for whole-video export (no frame loading)."""
    fps, total_frames = _ffprobe_video_metadata(video_file)
    session_name = sanitize_name(Path(video_file).stem)
    end_idx = total_frames - 2  # drop duplicate last frame
    cap = cv2.VideoCapture(video_file)
    return VideoState(
        cap=cap,
        path=video_file,
        fps=fps,
        window=FrameWindow(
            total_frames=total_frames,
            loaded_start=0,
            loaded_end=end_idx,
            current=0,
            base_step=max(1, int(round(fps))),
        ),
        clip=ClipRange(start=0, end=end_idx),
        frames={},
        loop=LoopCursor(anchor=time.monotonic()),
        suggestions=Suggestions(),
        session_name=session_name,
        session_path=str(SESSIONS_DIR / f"{session_name}.json"),
        original_session_payload={},
        skip_postprocess=True,
    )


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


def _run_clip_whole_export(video_file: str) -> None:
    """Run the export pipeline for a whole video (no editor UI)."""
    from .gui.export_dialog import ExportDialog
    from .gui.export_worker import connect_export

    state = build_clip_whole_state(video_file)
    dialog = ExportDialog()
    dialog.setWindowTitle("Exporting whole video")
    worker = connect_export(state, dialog)
    worker.start()
    dialog.exec()
    state.cap.release()


def launch_state() -> VideoState | None:
    ensure_runtime_dirs()
    last_session = LAST_SESSION_FILE.read_text(encoding="utf-8").strip() if LAST_SESSION_FILE.exists() else ""
    dialog = LauncherDialog(last_session=last_session)

    prefill = detect_nau_session_prefill()
    if prefill:
        dialog.session_name_edit.setText(prefill.session_name)
        dialog.video_file_edit.setText(prefill.video_file)
        dialog.timestamp_edit.setText(prefill.timestamp)
        dialog.new_radio.setChecked(True)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        raise SystemExit(0)
    info = dialog.build_result()
    if info["mode"] == "clip_whole":
        _run_clip_whole_export(info["video_file"])
        return None
    return build_state_from_launch_info(info)
