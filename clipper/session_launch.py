from __future__ import annotations

import time
from pathlib import Path

import cv2
from PyQt6.QtWidgets import QDialog

from .clip_range import ClipRange
from .create_session import create_session, ffprobe_video_metadata
from .frame_window import FrameWindow
from .gui.launcher_dialog import LauncherDialog
from .launch_choice import ClipWholeVideo, LaunchChoice, LoadSession, NewSession
from .loop_cursor import LoopCursor
from .nau_prefill import detect_nau_session_prefill
from .paths import LAST_SESSION_FILE, SESSIONS_DIR, ensure_runtime_dirs, sanitize_name
from .session_persistence import read_json
from .state import VideoState
from .state_factory import load_video_state
from .suggestions import Suggestions
from .timecode import parse_timestamp


def _load_state_from_session_file(session_path: Path) -> VideoState:
    payload = read_json(session_path)
    state = load_video_state(payload, session_path.stem)
    state.session_path = str(session_path)
    state.protect_existing_save_data = True
    return state


def build_clip_whole_state(video_file: str) -> VideoState:
    """Build a lightweight VideoState for whole-video export (no frame loading)."""
    fps, total_frames = ffprobe_video_metadata(video_file)
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


def build_state(choice: LoadSession | NewSession) -> VideoState:
    """Open what the launcher was asked for, and remember it for next time."""
    if isinstance(choice, LoadSession):
        session_path = Path(choice.session_json)
    else:
        session_path = create_session(
            choice.video_file,
            parse_timestamp(choice.timestamp),
            session_name=choice.session_name,
            seconds=choice.seconds,
            loop_mode=choice.loop_mode,
            vr=choice.vr,
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
    """The session the user chose, or None if there is no editor to open.

    None covers both of the two ways that happens -- the launcher was
    canceled, or a whole video was exported without an editor.  Cancel used to
    raise `SystemExit(0)` out of a function annotated `-> VideoState | None`,
    so it had three outcomes and its type said two, and `app.main` carried an
    `except SystemExit: raise` for it that never did anything (SystemExit is
    not an Exception, so it was never being caught).
    """
    ensure_runtime_dirs()
    last_session = LAST_SESSION_FILE.read_text(encoding="utf-8").strip() if LAST_SESSION_FILE.exists() else ""
    dialog = LauncherDialog(last_session=last_session)

    prefill = detect_nau_session_prefill()
    if prefill:
        dialog.prefill(prefill.session_name, prefill.video_file, prefill.timestamp)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    choice: LaunchChoice = dialog.build_result()
    if isinstance(choice, ClipWholeVideo):
        _run_clip_whole_export(choice.video_file)
        return None
    return build_state(choice)
