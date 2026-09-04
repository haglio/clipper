"""Main application window — assembles all widgets, handles keyboard dispatch."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QPainter, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)
from shared_ui.colors import (
    BORDER_DEFAULT,
    TIMELINE_ACTIVE,
    TIMELINE_LOADED,
)
from shared_ui.fonts import FONT_UI, SIZE_HEADING, make_font

from clipper.frame_store import safe_frame
from clipper.playback import current_loop_frame_index, loop_preview_indices
from clipper.timecode import format_seconds
from clipper.wrap_modes import WRAP_OVER_LOADED, wrap_bounds

from .button_bar import ButtonBar
from .exit_dialog import ExitDialog
from .export_dialog import ExportDialog
from .export_worker import connect_export
from .floating_controls import FloatingControlLayout
from .frame_converter import bgr_to_qimage, scale_to_fit
from .legend_widget import LegendWidget
from .main_window_style import (
    CHROME_STYLE,
    LABEL_STYLE,
    WARNING_STYLE,
    refuse_focus,
    size_controls,
    small_font,
)
from .shortcuts import BY_NAME, legend_rows, shortcut_for
from .timeline_controls import TimelineControls
from .timeline_widget import TimelineWidget
from .video_pane import VideoPane

if TYPE_CHECKING:
    from clipper.state import VideoState

# What asking for a frame can raise: a missing key or index from the cache, and
# `safe_frame`'s own RuntimeError when the frame is inside the loaded window but
# the decoder never produced it.
_UNDECODABLE = (KeyError, IndexError, RuntimeError)

class _WrapRow(QWidget):
    """Container that draws wrap-range brace lines and hosts the wrap button."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._x1 = 0
        self._x2 = 0

    def set_brace(self, x1: int, x2: int) -> None:
        self._x1 = x1
        self._x2 = x2
        self.update()

    def paintEvent(self, event) -> None:
        if self._x2 <= self._x1:
            return
        p = QPainter(self)
        pen = QPen(BORDER_DEFAULT, 1)
        p.setPen(pen)
        y = self.height() // 2
        p.drawLine(self._x1, y, self._x2, y)
        p.drawLine(self._x1, y - 8, self._x1, y + 8)
        p.drawLine(self._x2, y - 8, self._x2, y + 8)
        p.end()


class ClipperMainWindow(QMainWindow):
    """Main Clipper window containing all UI widgets."""

    def __init__(self, state: VideoState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setWindowTitle("Clipper")
        self.setMinimumSize(900, 600)
        self.resize(1520, 960)

        # Video panes
        self.left_pane = VideoPane()
        self.right_pane = VideoPane()

        # Timeline
        self.timeline = TimelineWidget()

        # Controls (created for signal management; buttons placed individually)
        self.button_bar = ButtonBar()
        self.timeline_controls = TimelineControls()
        self.legend = LegendWidget(legend_rows())

        # -- Labels ---------------------------------------------------------------

        self.session_label = QLabel(state.session_name)
        self.session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_label.setFont(make_font(FONT_UI, SIZE_HEADING, bold=True))

        self.file_info_label = QLabel(
            f"file: {os.path.basename(state.path)}    fps: {state.fps:.3f}"
        )
        self.file_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_info_label.setFont(small_font())
        self.file_info_label.setStyleSheet(LABEL_STYLE)

        self.cursor_label = QLabel()
        self.cursor_label.setFont(small_font())
        self.cursor_label.setStyleSheet(LABEL_STYLE)

        self.loop_label = QLabel()
        self.loop_label.setFont(small_font())
        self.loop_label.setStyleSheet(LABEL_STYLE)

        self.speed_label = QLabel()
        self.speed_label.setFont(small_font())
        self.speed_label.setStyleSheet(LABEL_STYLE)

        self.warning_label = QLabel()
        self.warning_label.setFont(small_font())
        self.warning_label.setStyleSheet(WARNING_STYLE)
        self.warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # -- Wire signals ---------------------------------------------------------

        # Each button runs the shortcut of the same name, so a button and its
        # key cannot come to mean different things.
        for signal, name in (
            (self.button_bar.speed_down_clicked, "speed_down"),
            (self.button_bar.speed_up_clicked, "speed_up"),
            (self.button_bar.play_pause_clicked, "play_pause"),
            (self.button_bar.export_clicked, "export"),
            (self.timeline_controls.extend_left_clicked, "extend_left"),
            (self.timeline_controls.contract_left_clicked, "contract_left"),
            (self.timeline_controls.extend_right_clicked, "extend_right"),
            (self.timeline_controls.contract_right_clicked, "contract_right"),
            (self.timeline_controls.shift_left_clicked, "shift_left"),
            (self.timeline_controls.shift_right_clicked, "shift_right"),
            (self.timeline_controls.mark_in_clicked, "mark_in"),
            (self.timeline_controls.mark_out_clicked, "mark_out"),
            (self.timeline_controls.wrap_clicked, "toggle_wrap"),
            (self.timeline_controls.loop_mode_clicked, "cycle_loop_mode"),
        ):
            signal.connect(self._runs(name))

        self.timeline.cursor_jumped.connect(self._on_timeline_click)

        # -- Layout ---------------------------------------------------------------

        central = QWidget()
        self.setCentralWidget(central)

        # Pane headers
        left_header = QLabel("frame at cursor")
        left_header.setFont(make_font(FONT_UI, SIZE_HEADING))
        left_header.setStyleSheet(LABEL_STYLE)
        left_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_header.setContentsMargins(0, 6, 0, 6)

        right_header = QLabel("loop preview")
        right_header.setFont(make_font(FONT_UI, SIZE_HEADING))
        right_header.setStyleSheet(LABEL_STYLE)
        right_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_header.setContentsMargins(0, 6, 0, 6)

        # Pane columns
        left_col = QVBoxLayout()
        left_col.setSpacing(2)
        left_col.addWidget(left_header)
        left_col.addWidget(self.left_pane, stretch=1)

        right_col = QVBoxLayout()
        right_col.setSpacing(2)
        right_col.addWidget(right_header)
        right_col.addWidget(self.right_pane, stretch=1)

        panes_row = QHBoxLayout()
        panes_row.addLayout(left_col, stretch=1)
        panes_row.addLayout(right_col, stretch=1)

        # Info row: cursor (left, stretch=1) | loop+speed+buttons (right, stretch=1)
        bb = self.button_bar
        tc = self.timeline_controls

        left_info = QVBoxLayout()
        left_info.setSpacing(0)
        left_info.addWidget(self.cursor_label)
        left_info.addStretch()

        right_info = QVBoxLayout()
        right_info.setSpacing(0)
        right_info.addWidget(self.loop_label)
        right_info.addWidget(self.speed_label)

        btn_group = QHBoxLayout()
        btn_group.setSpacing(4)
        btn_group.addWidget(bb.speed_down_btn)
        btn_group.addWidget(bb.speed_up_btn)
        btn_group.addWidget(bb.play_pause_btn)
        btn_group.addWidget(bb.export_btn)

        right_side = QHBoxLayout()
        right_side.addLayout(right_info)
        right_side.addStretch()
        right_side.addLayout(btn_group)

        info_row = QHBoxLayout()
        info_row.addLayout(left_info, stretch=1)
        info_row.addLayout(right_side, stretch=1)

        # Dynamic rows — buttons positioned in _update_button_positions()
        self._shift_row = QWidget()
        self._shift_row.setFixedHeight(32)
        tc.shift_left_btn.setParent(self._shift_row)
        tc.shift_right_btn.setParent(self._shift_row)

        # Timeline row (extend/contract on sides, static layout)
        timeline_row = QHBoxLayout()
        timeline_row.addWidget(tc.extend_left_btn)
        timeline_row.addWidget(tc.contract_left_btn)
        timeline_row.addWidget(self.timeline, stretch=1)
        timeline_row.addWidget(tc.contract_right_btn)
        timeline_row.addWidget(tc.extend_right_btn)

        self._mark_row = QWidget()
        self._mark_row.setFixedHeight(32)
        tc.mark_in_btn.setParent(self._mark_row)
        tc.mark_out_btn.setParent(self._mark_row)

        self._wrap_row = _WrapRow()
        self._wrap_row.setFixedHeight(36)
        tc.wrap_btn.setParent(self._wrap_row)

        # Loop mode (centered, static)
        mode_row = QHBoxLayout()
        mode_row.addStretch()
        mode_row.addWidget(tc.loop_mode_btn)
        mode_row.addStretch()

        # Assemble
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(2)
        main_layout.addWidget(self.session_label)
        main_layout.addWidget(self.file_info_label)
        main_layout.addLayout(panes_row, stretch=1)
        main_layout.addLayout(info_row)
        main_layout.addWidget(self._shift_row)
        main_layout.addLayout(timeline_row)
        main_layout.addWidget(self._mark_row)
        main_layout.addWidget(self._wrap_row)
        main_layout.addLayout(mode_row)
        main_layout.addWidget(self.warning_label)
        main_layout.addWidget(self.legend)

        self._floating = FloatingControlLayout(
            self.timeline, tc, self._shift_row, self._mark_row, self._wrap_row
        )

        central.setStyleSheet(CHROME_STYLE)
        size_controls(bb, tc)
        refuse_focus(self)

    @property
    def state(self) -> VideoState:
        """The session the window is editing -- what the shortcuts act on."""
        return self._state

    # -- Dynamic button positioning -------------------------------------------

    def update_button_positions(self) -> None:
        """Reposition shift/mark/wrap buttons relative to the timeline."""
        state = self._state
        wrap_from, wrap_to = wrap_bounds(state)
        self._floating.place(
            active_start=state.active_start,
            active_end=state.active_end,
            cursor=state.current,
            wrap_from=wrap_from,
            wrap_to=wrap_to,
            wrap_color=(
                TIMELINE_LOADED
                if state.wrap_mode == WRAP_OVER_LOADED
                else TIMELINE_ACTIVE
            ),
        )

    # -- Drawing the state ------------------------------------------------------

    def render(self, state: VideoState) -> None:
        """Push the state into every widget this window owns.

        `ClipperApp` used to do this from `_on_tick`: seventy lines binding
        `w = self.window` and then reaching two levels deep into twelve of its
        widgets, so the clock knew the window's widget names and the state's
        field names in equal measure.
        """
        loop_idx = self._draw_frames(state)
        self._draw_timeline(state, loop_idx)
        self._write_labels(state, loop_idx)
        self.button_bar.set_playing(not state.loop_paused)
        self.timeline_controls.set_loop_mode(state.loop_mode)
        self.warning_label.setText(state.session_warning)
        self.update_button_positions()

    def _draw_frames(self, state: VideoState) -> int:
        """Put the loop frame and the cursor frame in their panes.

        Returns the loop frame's index, which the timeline and the loop label
        both want.  A frame that will not decode costs its pane and nothing
        else -- including the RuntimeError `safe_frame` raises when the window
        spans a frame the decoder never produced, which this used to let out of
        a Qt slot and so out of the process.
        """
        loop_idx = state.active_start
        try:
            loop_idx = current_loop_frame_index(state)
            self._fill(self.right_pane, safe_frame(state, loop_idx))
        except _UNDECODABLE:
            pass
        try:
            self._fill(self.left_pane, safe_frame(state, state.current))
        except _UNDECODABLE:
            pass
        return loop_idx

    def _fill(self, pane: VideoPane, frame) -> None:
        image = bgr_to_qimage(frame)
        pane.set_frame(scale_to_fit(image, pane.width(), pane.height()))

    def _draw_timeline(self, state: VideoState, loop_idx: int) -> None:
        self.timeline.set_loaded_range(state.loaded_start, state.loaded_end)
        self.timeline.set_active_range(state.active_start, state.active_end)
        self.timeline.set_cursor_position(state.current)
        self.timeline.set_loop_position(loop_idx)
        self.timeline.set_suggestions(state.suggested_in, state.suggested_out)

    def _write_labels(self, state: VideoState, loop_idx: int) -> None:
        cursor_max = state.loaded_count - 1
        width = max(2, len(str(max(0, cursor_max))))
        self.cursor_label.setText(
            f"cursor: {state.current - state.loaded_start:0{width}d}/{cursor_max}"
            f" @ {format_seconds(state.current / state.fps)}"
        )

        # `_draw_frames` has just asked the loop cursor for its frame, and the
        # cursor settles its position on every path out of that call, so the
        # position is set whichever branch answered.
        preview_total = len(loop_preview_indices(state))
        width = max(2, len(str(max(0, preview_total))))
        self.loop_label.setText(
            f"loop frame: {state.paused_loop_pos:0{width}d}/{preview_total}"
            f" @ {format_seconds(loop_idx / state.fps)}"
        )

        playing = "playing" if not state.loop_paused else "paused"
        self.speed_label.setText(f"speed: {state.speed:.2f}x ({playing})")

    # -- Window events ---------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._state.should_prompt_on_exit:
            dialog = ExitDialog(self)
            dialog.exec()
            if dialog.choice == ExitDialog.SAVE:
                self._state.autosave_session()
            elif dialog.choice == ExitDialog.CANCEL:
                event.ignore()
                return
        event.accept()

    # -- Key dispatch ----------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        shortcut = shortcut_for(event.key(), event.text().lower())
        if shortcut is None:
            super().keyPressEvent(event)
            return
        shortcut.action(self)

    # -- Export ----------------------------------------------------------------

    def start_export(self) -> None:
        dialog = ExportDialog(self)
        worker = connect_export(self._state, dialog)
        self._export_worker = worker
        dialog.show()
        worker.start()

    # -- Helpers ---------------------------------------------------------------

    def _runs(self, name: str):
        """A slot that runs the named shortcut against this window."""
        shortcut = BY_NAME[name]
        return lambda: shortcut.action(self)

    def _on_timeline_click(self, idx: int) -> None:
        self._state.window.jump_to(idx)
        self._state.bump_render()
