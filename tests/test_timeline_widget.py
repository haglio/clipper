"""Tests for clipper.gui.timeline_widget — timeline bar display."""

from __future__ import annotations


import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

from clipper.gui.timeline_widget import TimelineWidget


@pytest.fixture()
def widget():
    w = TimelineWidget()
    w.resize(800, 40)
    return w


class TestCoordinateMapping:
    def test_x_for_index_at_start(self, widget):
        widget.set_loaded_range(0, 100)
        x = widget.x_for_index(0)
        assert x == 0

    def test_x_for_index_at_end(self, widget):
        widget.set_loaded_range(0, 100)
        x = widget.x_for_index(100)
        assert x == widget.width()

    def test_x_for_index_midpoint(self, widget):
        widget.set_loaded_range(0, 100)
        x = widget.x_for_index(50)
        assert abs(x - widget.width() // 2) <= 1

    def test_index_for_x_at_start(self, widget):
        widget.set_loaded_range(0, 100)
        idx = widget.index_for_x(0)
        assert idx == 0

    def test_index_for_x_at_end(self, widget):
        widget.set_loaded_range(0, 100)
        idx = widget.index_for_x(widget.width())
        assert idx == 100

    def test_index_for_x_clamped(self, widget):
        widget.set_loaded_range(10, 50)
        idx = widget.index_for_x(-100)
        assert idx == 10
        idx = widget.index_for_x(9999)
        assert idx == 50


class TestSetState:
    def test_set_loaded_range(self, widget):
        widget.set_loaded_range(10, 200)
        assert widget.loaded_start == 10
        assert widget.loaded_end == 200

    def test_set_active_range(self, widget):
        widget.set_active_range(20, 80)
        assert widget.active_start == 20
        assert widget.active_end == 80

    def test_set_cursor(self, widget):
        widget.set_cursor_position(42)
        assert widget.cursor_pos == 42

    def test_set_loop_position(self, widget):
        widget.set_loop_position(55)
        assert widget.loop_pos == 55

    def test_set_suggestions(self, widget):
        widget.set_suggestions(10, 90)
        assert widget.suggested_in == 10
        assert widget.suggested_out == 90


class TestClickSignal:
    def test_click_emits_cursor_jumped(self, widget, qtbot=None):
        widget.set_loaded_range(0, 100)
        results = []
        widget.cursor_jumped.connect(results.append)
        # Simulate a mouse press at midpoint
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPointF

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(widget.width() / 2, widget.height() / 2),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        widget.mousePressEvent(event)
        assert len(results) == 1
        assert abs(results[0] - 50) <= 1
