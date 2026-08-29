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
        """Called ~60fps — update loop preview frame and UI state."""
        from clipper.playback import current_loop_frame_index
        from clipper.frame_store import safe_frame
        from clipper.utils import format_seconds
        from .frame_converter import bgr_to_qimage, scale_to_fit

        state = self._state
        w = self.window

        # Update loop preview pane
        loop_idx = state.active_start
        try:
            loop_idx = current_loop_frame_index(state)
            loop_frame = safe_frame(state, loop_idx)
            qimg = bgr_to_qimage(loop_frame)
            scaled = scale_to_fit(qimg, w.right_pane.width(), w.right_pane.height())
            w.right_pane.set_frame(scaled)
        except (KeyError, IndexError):
            pass

        # Update cursor pane
        try:
            cursor_frame = safe_frame(state, state.current)
            qimg = bgr_to_qimage(cursor_frame)
            scaled = scale_to_fit(qimg, w.left_pane.width(), w.left_pane.height())
            w.left_pane.set_frame(scaled)
        except (KeyError, IndexError):
            pass

        # Sync timeline state
        w.timeline.set_loaded_range(state.loaded_start, state.loaded_end)
        w.timeline.set_active_range(state.active_start, state.active_end)
        w.timeline.set_cursor_position(state.current)
        w.timeline.set_loop_position(loop_idx)
        w.timeline.set_suggestions(state.suggested_in, state.suggested_out)
        w.timeline.set_wrap_mode(state.wrap_mode)

        # Sync controls
        w.button_bar.set_playing(not state.loop_paused)
        w.timeline_controls.set_loop_mode(state.loop_mode)

        # Update info labels
        cursor_rel = state.current - state.loaded_start
        cursor_max = state.loaded_count - 1
        cw = max(2, len(str(max(0, cursor_max))))
        cursor_ts = format_seconds(state.current / state.fps)
        w.cursor_label.setText(f"cursor: {cursor_rel:0{cw}d}/{cursor_max} @ {cursor_ts}")

        from clipper.playback import loop_preview_indices
        preview_seq = loop_preview_indices(state)
        preview_pos = (
            state.paused_loop_pos
            if state.paused_loop_pos is not None
            else (preview_seq.index(loop_idx) if loop_idx in preview_seq else 0)
        )
        preview_total = len(preview_seq)
        lw = max(2, len(str(max(0, preview_total))))
        loop_ts = format_seconds(loop_idx / state.fps)
        w.loop_label.setText(f"loop frame: {preview_pos:0{lw}d}/{preview_total} @ {loop_ts}")

        play_state = "playing" if not state.loop_paused else "paused"
        w.speed_label.setText(f"speed: {state.speed:.2f}x ({play_state})")

        # Warning label
        w.warning_label.setText(state.session_warning)

        # Reposition dynamic buttons (shift/mark/wrap)
        w.update_button_positions()
