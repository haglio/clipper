"""QThread-based export worker following Evolver's PipelineWorker pattern."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from clipper.state import VideoState


class ExportWorker(QThread):
    """Runs the export pipeline in a background thread, emitting progress signals."""

    stage_changed = pyqtSignal(str)
    clip_progress = pyqtSignal(float)
    fix_progress = pyqtSignal(float)
    audio_progress = pyqtSignal(float)
    export_finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, state: VideoState, parent=None):
        super().__init__(parent)
        self._state = state

    def run(self) -> None:
        from clipper.export_steps import (
            export_full_audio_mp3,
            export_raw_clip,
            run_clip_postprocess,
        )
        from clipper.paths import AUDIO_DIR, CLIPS_DIR, RAW_CLIPS_DIR, VR_CLIPS_DIR
        from clipper.state import ExportJob
        from clipper.utils import sanitize_name

        worker = self

        class _SignalBridge(ExportJob):
            """ExportJob subclass that forwards progress updates to Qt signals."""

            def __init__(self) -> None:
                object.__setattr__(self, "_w", worker)
                super().__init__(active=True, stage="preparing export")

            def __setattr__(self, name: str, value: object) -> None:
                super().__setattr__(name, value)
                try:
                    w = object.__getattribute__(self, "_w")
                except AttributeError:
                    return
                if name == "clip_progress":
                    w.clip_progress.emit(value)
                elif name == "fix_progress":
                    w.fix_progress.emit(value)
                elif name == "audio_progress":
                    w.audio_progress.emit(value)
                elif name == "stage":
                    w.stage_changed.emit(str(value))

        job = _SignalBridge()
        self._state.export_job = job

        session_base = sanitize_name(self._state.session_name)
        raw_path = RAW_CLIPS_DIR / f"{session_base}.mp4"
        clips_dir = VR_CLIPS_DIR if self._state.vr else CLIPS_DIR
        clip_path = clips_dir / f"{session_base}.mp4"
        audio_path = AUDIO_DIR / f"{session_base}.mp3"

        try:
            ok, detail = export_raw_clip(self._state, raw_path, job)
            if not ok:
                self.export_finished.emit(False, detail)
                return

            ok, detail = run_clip_postprocess(self._state, raw_path, clip_path, job)
            if not ok:
                self.export_finished.emit(False, detail)
                return

            ok, detail = export_full_audio_mp3(self._state, audio_path, job)
            if not ok:
                self.export_finished.emit(False, detail)
                return

            self.export_finished.emit(True, f"Done: {clip_path}")
        except Exception as exc:
            self.export_finished.emit(False, str(exc))
        finally:
            job.active = False
            job.done = True
