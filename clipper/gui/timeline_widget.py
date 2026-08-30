"""Custom-painted timeline bar showing loaded/active ranges, cursor, and suggestions."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from shared_ui.colors import (
    BG_PRIMARY,
    BORDER_TICK,
    BORDER_TIMELINE,
    TIMELINE_ACTIVE,
    TIMELINE_CURSOR,
    TIMELINE_LOADED,
    TIMELINE_LOOP,
    TIMELINE_SUGGESTED_IN,
    TIMELINE_SUGGESTED_OUT,
)


class TimelineWidget(QWidget):
    """Displays loaded/active ranges with cursor, loop position, and suggestions."""

    cursor_jumped = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.loaded_start: int = 0
        self.loaded_end: int = 0
        self.active_start: int = 0
        self.active_end: int = 0
        self.cursor_pos: int = 0
        self.loop_pos: int = 0
        self.suggested_in: int | None = None
        self.suggested_out: int | None = None
        self.setMinimumHeight(24)
        self.setFixedHeight(24)

    # -- Public setters -------------------------------------------------------

    def set_loaded_range(self, start: int, end: int) -> None:
        self.loaded_start = start
        self.loaded_end = end
        self.update()

    def set_active_range(self, start: int, end: int) -> None:
        self.active_start = start
        self.active_end = end
        self.update()

    def set_cursor_position(self, idx: int) -> None:
        self.cursor_pos = idx
        self.update()

    def set_loop_position(self, idx: int) -> None:
        self.loop_pos = idx
        self.update()

    def set_suggestions(self, in_idx: int | None, out_idx: int | None) -> None:
        self.suggested_in = in_idx
        self.suggested_out = out_idx
        self.update()

    # -- Coordinate mapping ---------------------------------------------------

    def x_for_index(self, idx: int) -> int:
        count = max(1, self.loaded_end - self.loaded_start)
        frac = (idx - self.loaded_start) / count
        return int(round(frac * self.width()))

    def index_for_x(self, x: int) -> int:
        x = max(0, min(self.width(), x))
        count = max(1, self.loaded_end - self.loaded_start)
        frac = x / self.width() if self.width() > 0 else 0.0
        idx = self.loaded_start + int(round(frac * count))
        return max(self.loaded_start, min(self.loaded_end, idx))

    # -- Events ---------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self.index_for_x(int(event.position().x()))
            self.cursor_jumped.emit(idx)

    # -- Painting -------------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(self.rect(), BG_PRIMARY)

        # Loaded range
        lx1 = self.x_for_index(self.loaded_start)
        lx2 = self.x_for_index(self.loaded_end)
        p.fillRect(lx1, 0, lx2 - lx1, h, TIMELINE_LOADED)

        # Active range
        ax1 = self.x_for_index(self.active_start)
        ax2 = self.x_for_index(self.active_end)
        p.fillRect(ax1, 0, ax2 - ax1, h, TIMELINE_ACTIVE)

        # Frame tick dots (top and bottom)
        tick_pen = QPen(BORDER_TICK, 1)
        p.setPen(tick_pen)
        for i in range(self.loaded_start, self.loaded_end + 1):
            tx = self.x_for_index(i)
            p.drawPoint(tx, 2)
            p.drawPoint(tx, h - 3)

        # Suggested in/out dotted lines
        if self.suggested_in is not None:
            self._draw_dotted_line(p, self.x_for_index(self.suggested_in), h, TIMELINE_SUGGESTED_IN)
        if self.suggested_out is not None:
            self._draw_dotted_line(p, self.x_for_index(self.suggested_out), h, TIMELINE_SUGGESTED_OUT)

        # Loop position
        loop_x = self.x_for_index(self.loop_pos)
        p.fillRect(loop_x - 1, 0, 3, h, TIMELINE_LOOP)

        # Cursor position (on top)
        cur_x = self.x_for_index(self.cursor_pos)
        p.fillRect(cur_x - 1, 0, 3, h, TIMELINE_CURSOR)

        # Outer border
        pen = QPen(BORDER_TIMELINE, 1)
        p.setPen(pen)
        p.drawRect(0, 0, w - 1, h - 1)

        p.end()

    def _draw_dotted_line(self, p: QPainter, x: int, h: int, color: QColor) -> None:
        pen = QPen(color, 2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(x, 0, x, h)
