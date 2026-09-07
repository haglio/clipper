"""Runs the three export steps off the Qt thread, reporting progress by signal."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from clipper.state import VideoState


def connect_export(state: VideoState, dialog) -> ExportWorker:
    """A worker for `state` that reports its progress into `dialog`.

    These nine lines were written out twice -- once in the main window and once
    in the whole-video path that has no window -- including the identical
    two-call lambda.

    It does not start the worker.  The caller does, because the caller is also
    what keeps it alive: a QThread whose last Python reference goes out of
    scope while it is running is collected mid-export, so the returned object
    has to be held somewhere either way.
    """
    worker = ExportWorker(state)
    worker.stage_changed.connect(dialog.set_stage)
    worker.clip_progress.connect(dialog.set_clip_progress)
    worker.fix_progress.connect(dialog.set_fix_progress)
    worker.audio_progress.connect(dialog.set_audio_progress)
    worker.export_finished.connect(
        lambda ok, msg: (dialog.set_done(ok), dialog.set_error("" if ok else msg))
    )
    return worker


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

    # -- The progress an export reports (clipper.export_progress.ExportProgress)

    def stage(self, text: str) -> None:
        self.stage_changed.emit(text)

    def clip(self, fraction: float) -> None:
        self.clip_progress.emit(fraction)

    def fix(self, fraction: float) -> None:
        self.fix_progress.emit(fraction)

    def audio(self, fraction: float) -> None:
        self.audio_progress.emit(fraction)

    def run(self) -> None:
        from clipper.export_pipeline import run_export

        ok, message = run_export(self._state, self)
        self.export_finished.emit(ok, message)
