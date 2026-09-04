"""Tests for clipper.gui.timeline_widget — timeline bar display."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from shared_ui.colors import (
    TIMELINE_ACTIVE,
    TIMELINE_CURSOR,
    TIMELINE_LOADED,
    TIMELINE_LOOP,
    TIMELINE_SUGGESTED_IN,
    TIMELINE_SUGGESTED_OUT,
)

from clipper.gui.timeline_widget import TimelineWidget


@pytest.fixture
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
    def test_click_emits_cursor_jumped(self, widget):
        widget.set_loaded_range(0, 100)
        results = []
        widget.cursor_jumped.connect(results.append)

        widget.mousePressEvent(QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(widget.width() / 2, widget.height() / 2),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ))

        assert len(results) == 1
        assert abs(results[0] - 50) <= 1

    def test_a_right_click_moves_nothing(self, widget):
        widget.set_loaded_range(0, 100)
        results = []
        widget.cursor_jumped.connect(results.append)

        widget.mousePressEvent(QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(widget.width() / 2, widget.height() / 2),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        ))

        assert results == []


class TestPainting:
    """The bands and lines the user actually reads the timeline by.

    Nothing asserted a painted pixel, so replacing ``paintEvent``'s body with
    ``return`` was caught only by the dead-code guard.
    """

    @pytest.fixture
    def painted(self, widget, rendered):
        widget.set_loaded_range(0, 100)
        widget.set_active_range(20, 80)
        widget.set_cursor_position(50)
        widget.set_loop_position(30)
        widget.set_suggestions(10, 90)
        return rendered(widget)

    def _band(self, image, x):
        """The color mid-height, clear of the tick dots along both edges."""
        return image.pixelColor(x, 12).name()

    def test_the_loaded_range_is_drawn_outside_the_active_one(self, painted):
        assert self._band(painted, 40) == TIMELINE_LOADED.name()
        assert self._band(painted, 700) == TIMELINE_LOADED.name()

    def test_the_active_range_is_drawn_over_it(self, painted):
        assert self._band(painted, 300) == TIMELINE_ACTIVE.name()
        assert self._band(painted, 500) == TIMELINE_ACTIVE.name()

    def test_the_active_band_starts_and_ends_where_its_marks_are(self, painted, widget):
        just_inside = widget.x_for_index(20) + 3
        just_outside = widget.x_for_index(20) - 3

        assert self._band(painted, just_inside) == TIMELINE_ACTIVE.name()
        assert self._band(painted, just_outside) == TIMELINE_LOADED.name()

    def test_the_cursor_is_drawn_where_it_sits(self, painted, widget):
        assert self._band(painted, widget.x_for_index(50)) == TIMELINE_CURSOR.name()

    def test_the_loop_position_is_drawn_where_it_sits(self, painted, widget):
        assert self._band(painted, widget.x_for_index(30)) == TIMELINE_LOOP.name()

    def test_both_suggestions_are_drawn_where_they_sit(self, painted, widget):
        assert self._band(painted, widget.x_for_index(10)) == TIMELINE_SUGGESTED_IN.name()
        assert self._band(painted, widget.x_for_index(90)) == TIMELINE_SUGGESTED_OUT.name()

    def test_no_suggestion_lines_appear_when_there_are_none(self, widget, rendered):
        widget.set_loaded_range(0, 100)
        widget.set_active_range(20, 80)
        widget.set_cursor_position(50)
        widget.set_loop_position(30)
        widget.set_suggestions(None, None)

        image = rendered(widget)

        drawn = {image.pixelColor(x, 12).name() for x in range(4, 796)}
        assert TIMELINE_SUGGESTED_IN.name() not in drawn
        assert TIMELINE_SUGGESTED_OUT.name() not in drawn

    def test_the_cursor_is_drawn_on_top_of_the_loop_position(self, widget, rendered):
        widget.set_loaded_range(0, 100)
        widget.set_active_range(20, 80)
        widget.set_loop_position(50)
        widget.set_cursor_position(50)

        image = rendered(widget)

        assert self._band(image, widget.x_for_index(50)) == TIMELINE_CURSOR.name()
