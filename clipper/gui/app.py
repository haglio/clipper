"""ClipperApp — wires all GUI components together, following Evolver's pattern."""

from __future__ import annotations

import ctypes
import sys
from typing import TYPE_CHECKING

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from .main_window import ClipperMainWindow
from .playback_timer import PlaybackTimer

if TYPE_CHECKING:
    from clipper.state import VideoState


class ClipperApp:
    """Creates QApplication, main window, and playback timer."""

    def __init__(self, state: VideoState):
        self._state = state

        # Set Windows App ID for taskbar grouping
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Clipper.VideoEditor"
            )
        except (AttributeError, OSError):
            pass

        self._app = QApplication.instance()
        if self._app is None:
            self._app = QApplication(sys.argv)
        self._app.setApplicationName("Clipper")

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
        """Called ~60fps — update loop preview frame and UI state."""
        from clipper.playback import current_loop_frame_index
        from clipper.frame_store import safe_frame
        from .frame_converter import bgr_to_qimage, scale_to_fit

        state = self._state

        # Update loop preview pane
        try:
            loop_idx = current_loop_frame_index(state)
            loop_frame = safe_frame(state, loop_idx)
            qimg = bgr_to_qimage(loop_frame)
            scaled = scale_to_fit(qimg, self.window.right_pane.width(), self.window.right_pane.height())
            self.window.right_pane.set_frame(scaled)
        except (KeyError, IndexError):
            pass

        # Update cursor pane (only if state changed)
        try:
            cursor_frame = safe_frame(state, state.current)
            qimg = bgr_to_qimage(cursor_frame)
            scaled = scale_to_fit(qimg, self.window.left_pane.width(), self.window.left_pane.height())
            self.window.left_pane.set_frame(scaled)
        except (KeyError, IndexError):
            pass

        # Sync timeline state
        self.window.timeline.set_loaded_range(state.loaded_start, state.loaded_end)
        self.window.timeline.set_active_range(state.active_start, state.active_end)
        self.window.timeline.set_cursor_position(state.current)
        self.window.timeline.set_suggestions(state.suggested_in, state.suggested_out)
        self.window.timeline.set_wrap_mode(state.wrap_mode)

        # Sync controls
        self.window.button_bar.set_playing(not state.loop_paused)
        self.window.timeline_controls.set_wrap_mode(state.wrap_mode)
        self.window.timeline_controls.set_loop_mode(state.loop_mode)
