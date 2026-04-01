"""QTimer-driven playback loop replacing cv2.waitKeyEx polling."""

from __future__ import annotations

from PyQt6.QtCore import QTimer, pyqtSignal, QObject


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

    def is_running(self) -> bool:
        return self._timer.isActive()
