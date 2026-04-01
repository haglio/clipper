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

        try:
            self.stage_changed.emit("Exporting raw clip...")
            raw_output = export_raw_clip(
                self._state,
                progress_cb=lambda p: self.clip_progress.emit(p),
            )

            self.stage_changed.emit("Normalizing clip...")
            clip_output = run_clip_postprocess(
                self._state,
                raw_output,
                progress_cb=lambda p: self.fix_progress.emit(p),
            )

            self.stage_changed.emit("Extracting audio...")
            audio_output = export_full_audio_mp3(
                self._state,
                progress_cb=lambda p: self.audio_progress.emit(p),
            )

            self.export_finished.emit(True, f"Done: {clip_output}")
        except Exception as exc:
            self.export_finished.emit(False, str(exc))
