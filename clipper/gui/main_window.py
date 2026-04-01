"""Main application window — assembles all widgets, handles keyboard dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from shared_ui.colors import BG_PRIMARY

from clipper.editing import (
    accept_suggested_in,
    accept_suggested_out,
    cycle_loop_mode,
    set_mark_in,
    set_mark_out,
    shift_active_range,
)
from clipper.export import start_export_job
from clipper.loaded_bounds import contract_left, contract_right, extend_left, extend_right
from clipper.navigation import move_current_left, move_current_right, toggle_wrap_mode
from clipper.playback import change_speed, toggle_loop_pause

from .button_bar import ButtonBar
from .legend_widget import LegendWidget
from .timeline_controls import TimelineControls
from .timeline_widget import TimelineWidget
from .video_pane import VideoPane

if TYPE_CHECKING:
    from clipper.state import VideoState


class ClipperMainWindow(QMainWindow):
    """Main Clipper window containing all UI widgets."""

    def __init__(self, state: VideoState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setWindowTitle(f"Clipper — {state.session_name}")
        self.setMinimumSize(900, 600)

        # Video panes
        self.left_pane = VideoPane()
        self.right_pane = VideoPane()

        # Timeline
        self.timeline = TimelineWidget()

        # Controls
        self.button_bar = ButtonBar()
        self.timeline_controls = TimelineControls()
        self.legend = LegendWidget()

        # Info labels
        self.session_label = QLabel(state.session_name)
        self.session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cursor_label = QLabel()
        self.loop_label = QLabel()
        self.warning_label = QLabel()

        # Wire button signals
        self.button_bar.speed_down_clicked.connect(lambda: self._dispatch(change_speed, -0.25))
        self.button_bar.speed_up_clicked.connect(lambda: self._dispatch(change_speed, 0.25))
        self.button_bar.play_pause_clicked.connect(lambda: self._dispatch_simple(toggle_loop_pause))
        self.button_bar.export_clicked.connect(lambda: self._dispatch_simple(start_export_job))

        self.timeline_controls.extend_left_clicked.connect(lambda: self._dispatch_simple(extend_left))
        self.timeline_controls.contract_left_clicked.connect(lambda: self._dispatch_simple(contract_left))
        self.timeline_controls.extend_right_clicked.connect(lambda: self._dispatch_simple(extend_right))
        self.timeline_controls.contract_right_clicked.connect(lambda: self._dispatch_simple(contract_right))
        self.timeline_controls.shift_left_clicked.connect(lambda: self._dispatch(shift_active_range, -1))
        self.timeline_controls.shift_right_clicked.connect(lambda: self._dispatch(shift_active_range, 1))
        self.timeline_controls.mark_in_clicked.connect(lambda: self._dispatch_simple(set_mark_in))
        self.timeline_controls.mark_out_clicked.connect(lambda: self._dispatch_simple(set_mark_out))
        self.timeline_controls.wrap_clicked.connect(lambda: self._dispatch_simple(toggle_wrap_mode))
        self.timeline_controls.loop_mode_clicked.connect(lambda: self._dispatch_simple(cycle_loop_mode))

        self.timeline.cursor_jumped.connect(self._on_timeline_click)

        # Layout
        central = QWidget()
        self.setCentralWidget(central)

        # Panes row
        left_col = QVBoxLayout()
        left_col.addWidget(QLabel("frame at cursor"))
        left_col.addWidget(self.left_pane, stretch=1)
        left_col.addWidget(self.cursor_label)

        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("loop preview"))
        right_col.addWidget(self.right_pane, stretch=1)
        right_col.addWidget(self.loop_label)
        right_col.addWidget(self.button_bar)

        panes_row = QHBoxLayout()
        panes_row.addLayout(left_col, stretch=1)
        panes_row.addLayout(right_col, stretch=1)

        main_layout = QVBoxLayout(central)
        main_layout.addWidget(self.session_label)
        main_layout.addLayout(panes_row, stretch=1)
        main_layout.addWidget(self.timeline_controls)
        main_layout.addWidget(self.timeline)
        main_layout.addWidget(self.legend)
        main_layout.addWidget(self.warning_label)

        # Set dark background
        central.setStyleSheet(f"background-color: {BG_PRIMARY.name()};")

    # -- Key dispatch ----------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        text = event.text().lower()

        if key == Qt.Key.Key_Left:
            move_current_left(self._state)
        elif key == Qt.Key.Key_Right:
            move_current_right(self._state)
        elif key == Qt.Key.Key_Space:
            toggle_loop_pause(self._state)
        elif text == "a":
            extend_left(self._state)
        elif text == "s":
            contract_left(self._state)
        elif text == "d":
            contract_right(self._state)
        elif text == "f":
            extend_right(self._state)
        elif text in ("i", "["):
            set_mark_in(self._state)
        elif text in ("o", "]"):
            set_mark_out(self._state)
        elif text == "9" or text == "(":
            accept_suggested_in(self._state)
        elif text == "0" or text == ")":
            accept_suggested_out(self._state)
        elif text in (",", "<"):
            shift_active_range(self._state, -1)
        elif text in (".", ">"):
            shift_active_range(self._state, 1)
        elif text == "w":
            toggle_wrap_mode(self._state)
        elif text == "l":
            cycle_loop_mode(self._state)
        elif text in ("-", "_"):
            change_speed(self._state, -0.25)
        elif text in ("+", "="):
            change_speed(self._state, 0.25)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            start_export_job(self._state)
        elif key == Qt.Key.Key_Escape:
            if self._state.export_job and not self._state.export_job.dismissed:
                self._state.export_job.dismissed = True
        elif text == "q":
            self.close()
        else:
            super().keyPressEvent(event)

    # -- Helpers ---------------------------------------------------------------

    def _dispatch_simple(self, fn) -> None:
        fn(self._state)

    def _dispatch(self, fn, *args) -> None:
        fn(self._state, *args)

    def _on_timeline_click(self, idx: int) -> None:
        self._state.current = idx
        self._state.render_rev += 1
