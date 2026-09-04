"""The buttons that follow the timeline: shift, mark in/out, and wrap.

They are placed by hand in pixels rather than by a layout, because each one
tracks a position on the timeline rather than a slot in a row.  That is one of
the six things `ClipperMainWindow` was doing; here it knows nothing about a
`VideoState` beyond the five indices and the color it is handed.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget
from shared_ui.colors import BORDER_SUBTLE

GAP = 4


class FloatingControlLayout:
    """Places the shift, mark and wrap buttons against timeline coordinates."""

    def __init__(self, timeline, controls, shift_row: QWidget,
                 mark_row: QWidget, wrap_row) -> None:
        self._timeline = timeline
        self._controls = controls
        self._shift_row = shift_row
        self._mark_row = mark_row
        self._wrap_row = wrap_row

    def place(self, *, active_start: int, active_end: int, cursor: int,
              wrap_from: int, wrap_to: int, wrap_color: QColor) -> None:
        """Move every floating button to where its index now is.

        Does nothing before the timeline has a width -- there is nowhere to
        map an index to yet.
        """
        if self._timeline.width() <= 0:
            return
        self._place_shift(active_start, active_end)
        self._place_marks(active_start, active_end, cursor)
        self._place_wrap(wrap_from, wrap_to, wrap_color)

    def _offset_in(self, row: QWidget) -> int:
        """X offset of the timeline's origin in `row`'s coordinate system."""
        return row.mapFromGlobal(self._timeline.mapToGlobal(QPoint(0, 0))).x()

    def _place_shift(self, active_start: int, active_end: int) -> None:
        """Straddling the midpoint of the active range."""
        tl, tc = self._timeline, self._controls
        center = self._offset_in(self._shift_row) + (
            tl.x_for_index(active_start) + tl.x_for_index(active_end)
        ) // 2
        width = tc.shift_left_btn.width()
        y = (self._shift_row.height() - tc.shift_left_btn.height()) // 2
        tc.shift_left_btn.move(center - GAP // 2 - width, y)
        tc.shift_right_btn.move(center + GAP // 2, y)
        tc.shift_left_btn.show()
        tc.shift_right_btn.show()

    def _place_marks(self, active_start: int, active_end: int, cursor: int) -> None:
        """Straddling the cursor inside the range; split around it outside."""
        tl, tc = self._timeline, self._controls
        offset = self._offset_in(self._mark_row)
        cursor_x = offset + tl.x_for_index(cursor)
        width = tc.mark_in_btn.width()
        y = (self._mark_row.height() - tc.mark_in_btn.height()) // 2

        if cursor < active_start:
            start_x = offset + tl.x_for_index(active_start)
            tc.mark_in_btn.move(cursor_x - width // 2, y)
            tc.mark_out_btn.move(start_x - width // 2, y)
        elif cursor > active_end:
            end_x = offset + tl.x_for_index(active_end)
            tc.mark_in_btn.move(end_x - width // 2, y)
            tc.mark_out_btn.move(cursor_x - width // 2, y)
        else:
            tc.mark_in_btn.move(cursor_x - GAP // 2 - width, y)
            tc.mark_out_btn.move(cursor_x + GAP // 2, y)
        tc.mark_in_btn.setEnabled(cursor < active_end)
        tc.mark_out_btn.setEnabled(cursor > active_start)
        tc.mark_in_btn.show()
        tc.mark_out_btn.show()

    def _place_wrap(self, wrap_from: int, wrap_to: int, color: QColor) -> None:
        """Centered on the range the cursor wraps within, painted to match it."""
        tl, tc = self._timeline, self._controls
        offset = self._offset_in(self._wrap_row)
        x1 = offset + tl.x_for_index(wrap_from)
        x2 = offset + tl.x_for_index(wrap_to)
        y = (self._wrap_row.height() - tc.wrap_btn.height()) // 2
        tc.wrap_btn.move((x1 + x2) // 2 - tc.wrap_btn.width() // 2, y)
        tc.wrap_btn.setStyleSheet(
            f"background: {color.name()}; border: 1px solid {BORDER_SUBTLE.name()};"
        )
        tc.wrap_btn.show()
        self._wrap_row.set_brace(x1, x2)
