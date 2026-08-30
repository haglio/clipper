"""Main application window — assembles all widgets, handles keyboard dispatch."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeyEvent, QPainter, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shared_ui.colors import (
    RED,
    BG_BUTTON,
    BG_BUTTON_ACTIVE,
    BG_KEYCAP,
    BG_PRIMARY,
    BG_TERTIARY,
    BORDER_DEFAULT,
    BORDER_SUBTLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TIMELINE_ACTIVE,
    TIMELINE_LOADED,
)
from shared_ui.fonts import FONT_UI, SIZE_HEADING, SIZE_SMALL, make_font

from clipper.editing import (
    accept_suggested_in,
    accept_suggested_out,
    cycle_loop_mode,
    set_mark_in,
    set_mark_out,
    shift_active_range,
)
from clipper.loaded_bounds import contract_left, contract_right, extend_left, extend_right
from clipper.navigation import move_current_left, move_current_right, toggle_wrap_mode
from clipper.playback import change_speed, toggle_loop_pause

from .button_bar import ButtonBar
from .exit_dialog import ExitDialog
from .export_dialog import ExportDialog
from .export_worker import ExportWorker
from .legend_widget import LegendWidget
from .timeline_controls import TimelineControls
from .timeline_widget import TimelineWidget
from .video_pane import VideoPane

if TYPE_CHECKING:
    from clipper.state import VideoState

_LABEL_STYLE = f"color: {TEXT_SECONDARY.name()}; background: transparent;"
_UI_FONT_SM = make_font(FONT_UI, SIZE_SMALL)
_BTN_STYLE = f"""
    QPushButton {{
        font-family: "{FONT_UI}";
        font-size: {SIZE_SMALL}pt;
        color: {TEXT_PRIMARY.name()};
        background: {BG_BUTTON.name()};
        border: 1px solid {BORDER_SUBTLE.name()};
        padding: 3px 8px;
        min-height: 22px;
    }}
    QPushButton:hover {{ background: {BG_KEYCAP.name()}; }}
    QPushButton:pressed {{ background: {BG_TERTIARY.name()}; }}
    /* One rule across the family: a control that is ON sits on a lighter ground
       than one at rest, so a toggled button reads the same whichever app it is
       in. */
    QPushButton:checked {{ background: {BG_BUTTON_ACTIVE.name()}; }}
"""


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
        self.legend = LegendWidget()

        # -- Labels ---------------------------------------------------------------

        self.session_label = QLabel(state.session_name)
        self.session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_label.setFont(make_font(FONT_UI, SIZE_HEADING, bold=True))

        self.file_info_label = QLabel(
            f"file: {os.path.basename(state.path)}    fps: {state.fps:.3f}"
        )
        self.file_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_info_label.setFont(_UI_FONT_SM)
        self.file_info_label.setStyleSheet(_LABEL_STYLE)

        self.cursor_label = QLabel()
        self.cursor_label.setFont(_UI_FONT_SM)
        self.cursor_label.setStyleSheet(_LABEL_STYLE)

        self.loop_label = QLabel()
        self.loop_label.setFont(_UI_FONT_SM)
        self.loop_label.setStyleSheet(_LABEL_STYLE)

        self.speed_label = QLabel()
        self.speed_label.setFont(_UI_FONT_SM)
        self.speed_label.setStyleSheet(_LABEL_STYLE)

        self.warning_label = QLabel()
        self.warning_label.setFont(_UI_FONT_SM)
        self.warning_label.setStyleSheet(
            f"color: {RED.name()}; background: transparent;"
        )
        self.warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # -- Wire signals ---------------------------------------------------------

        self.button_bar.speed_down_clicked.connect(lambda: self._dispatch(change_speed, -0.25))
        self.button_bar.speed_up_clicked.connect(lambda: self._dispatch(change_speed, 0.25))
        self.button_bar.play_pause_clicked.connect(lambda: self._dispatch_simple(toggle_loop_pause))
        self.button_bar.export_clicked.connect(self._on_export)

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

        # -- Layout ---------------------------------------------------------------

        central = QWidget()
        self.setCentralWidget(central)

        # Pane headers
        left_header = QLabel("frame at cursor")
        left_header.setFont(make_font(FONT_UI, SIZE_HEADING))
        left_header.setStyleSheet(_LABEL_STYLE)
        left_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_header.setContentsMargins(0, 6, 0, 6)

        right_header = QLabel("loop preview")
        right_header.setFont(make_font(FONT_UI, SIZE_HEADING))
        right_header.setStyleSheet(_LABEL_STYLE)
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

        # Apply button styling
        central.setStyleSheet(
            f"background-color: {BG_PRIMARY.name()}; color: {TEXT_PRIMARY.name()};"
            + _BTN_STYLE
        )

        # Compact square buttons for the small controls
        for btn in (tc.shift_left_btn, tc.shift_right_btn,
                    tc.extend_left_btn, tc.contract_left_btn,
                    tc.contract_right_btn, tc.extend_right_btn,
                    tc.mark_in_btn, tc.mark_out_btn,
                    bb.speed_down_btn, bb.speed_up_btn):
            btn.setFixedSize(32, 28)
        bb.play_pause_btn.setFixedSize(40, 28)
        bb.export_btn.setFixedSize(72, 28)
        tc.wrap_btn.setFixedSize(64, 28)

        # Every key must reach keyPressEvent, so no button takes focus.
        for btn in self.findChildren(QPushButton):
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    # -- Dynamic button positioning -------------------------------------------

    def update_button_positions(self) -> None:
        """Reposition shift/mark/wrap buttons relative to the timeline."""
        state = self._state
        tl = self.timeline
        tc = self.timeline_controls

        if tl.width() <= 0:
            return

        def _tl_offset(target: QWidget) -> int:
            """X offset of the timeline's origin in target's coordinate system."""
            return target.mapFromGlobal(tl.mapToGlobal(QPoint(0, 0))).x()

        # -- Shift buttons: center on active range midpoint --
        in_x = tl.x_for_index(state.active_start)
        out_x = tl.x_for_index(state.active_end)

        off = _tl_offset(self._shift_row)
        shift_center = off + (in_x + out_x) // 2
        btn_w = tc.shift_left_btn.width()
        gap = 4
        y = (self._shift_row.height() - tc.shift_left_btn.height()) // 2
        tc.shift_left_btn.move(shift_center - gap // 2 - btn_w, y)
        tc.shift_right_btn.move(shift_center + gap // 2, y)
        tc.shift_left_btn.show()
        tc.shift_right_btn.show()

        # -- Mark buttons: follow cursor with three-case logic --
        off = _tl_offset(self._mark_row)
        cur_x = off + tl.x_for_index(state.current)
        mbw = tc.mark_in_btn.width()
        mgap = 4
        my = (self._mark_row.height() - tc.mark_in_btn.height()) // 2

        if state.current < state.active_start:
            left_x = off + tl.x_for_index(state.active_start)
            tc.mark_in_btn.move(cur_x - mbw // 2, my)
            tc.mark_out_btn.move(left_x - mbw // 2, my)
        elif state.current > state.active_end:
            right_x = off + tl.x_for_index(state.active_end)
            tc.mark_in_btn.move(right_x - mbw // 2, my)
            tc.mark_out_btn.move(cur_x - mbw // 2, my)
        else:
            tc.mark_in_btn.move(cur_x - mgap // 2 - mbw, my)
            tc.mark_out_btn.move(cur_x + mgap // 2, my)
        tc.mark_in_btn.setEnabled(state.current < state.active_end)
        tc.mark_out_btn.setEnabled(state.current > state.active_start)
        tc.mark_in_btn.show()
        tc.mark_out_btn.show()

        # -- Wrap button: center on wrap range, color by mode --
        if state.wrap_mode == "blue":
            wrap_lo, wrap_hi = state.loaded_start, state.loaded_end
            wrap_color = TIMELINE_LOADED
        else:
            wrap_lo, wrap_hi = state.active_start, state.active_end
            wrap_color = TIMELINE_ACTIVE

        off = _tl_offset(self._wrap_row)
        wx1 = off + tl.x_for_index(wrap_lo)
        wx2 = off + tl.x_for_index(wrap_hi)
        wrap_center = (wx1 + wx2) // 2
        wy = (self._wrap_row.height() - tc.wrap_btn.height()) // 2
        tc.wrap_btn.move(wrap_center - tc.wrap_btn.width() // 2, wy)
        tc.wrap_btn.setStyleSheet(
            f"background: {wrap_color.name()}; border: 1px solid {BORDER_SUBTLE.name()};"
        )
        tc.wrap_btn.show()

        self._wrap_row.set_brace(wx1, wx2)

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
            self._on_export()
        elif text == "q":
            self.close()
        else:
            super().keyPressEvent(event)

    # -- Export ----------------------------------------------------------------

    def _on_export(self) -> None:
        dialog = ExportDialog(self)
        worker = ExportWorker(self._state)
        worker.stage_changed.connect(dialog.set_stage)
        worker.clip_progress.connect(dialog.set_clip_progress)
        worker.fix_progress.connect(dialog.set_fix_progress)
        worker.audio_progress.connect(dialog.set_audio_progress)
        worker.export_finished.connect(
            lambda ok, msg: (dialog.set_done(ok), dialog.set_error("" if ok else msg))
        )
        self._export_worker = worker
        dialog.show()
        worker.start()

    # -- Helpers ---------------------------------------------------------------

    def _dispatch_simple(self, fn) -> None:
        fn(self._state)

    def _dispatch(self, fn, *args) -> None:
        fn(self._state, *args)

    def _on_timeline_click(self, idx: int) -> None:
        self._state.window.jump_to(idx)
        self._state.render_rev += 1
