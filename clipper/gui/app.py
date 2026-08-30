"""ClipperApp — owns the QApplication, the window and the playback clock."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from clipper.window_icons import clipper_icon_path

from .main_window import ClipperMainWindow
from .playback_timer import PlaybackTimer

if TYPE_CHECKING:
    from clipper.state import VideoState


class ClipperApp:
    """Creates QApplication, main window, and playback timer."""

    def __init__(self, state: VideoState):
        self._state = state

        # AppUserModelID is already set by app.main() before we get here;
        # do NOT override it — it must stay "FunTime.Clipper" to match the
        # shortcut so Windows groups the taskbar entry correctly.

        self._app = QApplication.instance()
        if self._app is None:
            self._app = QApplication(sys.argv)
        self._app.setApplicationName("Clipper")

        icon_path = clipper_icon_path()
        if icon_path.exists():
            self._app.setWindowIcon(QIcon(str(icon_path)))

        self.window = ClipperMainWindow(state)
        self.playback_timer = PlaybackTimer()

        # Wire playback timer tick to frame update
        self.playback_timer.tick.connect(self._on_tick)

    def run(self) -> int:
        """Show the window and enter the event loop."""
        self.window.show()
        self.playback_timer.start()
        return self._app.exec()

    def _on_tick(self) -> None:
        """Called ~60fps -- redraw the window from the state."""
        self.window.render(self._state)
