"""The clock the loop preview runs on: a tick at ~60 fps, and nothing else."""

from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class PlaybackTimer(QObject):
    """Fires a tick signal at ~60fps for the playback animation loop."""

    tick = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.interval_ms = 16  # ~60fps ceiling
        self._timer = QTimer(self)
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self.tick)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
