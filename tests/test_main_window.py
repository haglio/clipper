"""Tests for clipper.gui.main_window — main application window."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from clipper.gui.main_window import ClipperMainWindow


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def mock_state():
    state = MagicMock()
    state.session_name = "test_session"
    state.path = "/video.mp4"
    state.fps = 30.0
    state.total_frames = 300
    state.loaded_start = 0
    state.loaded_end = 100
    state.active_start = 20
    state.active_end = 80
    state.current = 50
    state.loop_mode = "base-tip-base"
    state.wrap_mode = "blue"
    state.speed = 1.0
    state.loop_paused = False
    state.suggested_in = None
    state.suggested_out = None
    state.export_job = None
    state.dirty = False
    state.should_prompt_on_exit = False
    state.session_warning = ""
    return state


@pytest.fixture()
def window(mock_state):
    w = ClipperMainWindow(mock_state)
    return w


class TestConstruction:
    def test_has_video_panes(self, window):
        assert window.left_pane is not None
        assert window.right_pane is not None

    def test_has_timeline(self, window):
        assert window.timeline is not None

    def test_has_button_bar(self, window):
        assert window.button_bar is not None

    def test_has_timeline_controls(self, window):
        assert window.timeline_controls is not None

    def test_has_legend(self, window):
        assert window.legend is not None

    def test_window_title(self, window):
        assert "test_session" in window.windowTitle().lower() or "clipper" in window.windowTitle().lower()


class TestKeyDispatch:
    def _press(self, window, key, text=""):
        event = QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, text)
        window.keyPressEvent(event)

    def test_left_arrow_calls_move_left(self, window, mock_state):
        with patch("clipper.gui.main_window.move_current_left") as mock:
            self._press(window, Qt.Key.Key_Left)
            mock.assert_called_once_with(mock_state)

    def test_right_arrow_calls_move_right(self, window, mock_state):
        with patch("clipper.gui.main_window.move_current_right") as mock:
            self._press(window, Qt.Key.Key_Right)
            mock.assert_called_once_with(mock_state)

    def test_space_toggles_playback(self, window, mock_state):
        with patch("clipper.gui.main_window.toggle_loop_pause") as mock:
            self._press(window, Qt.Key.Key_Space)
            mock.assert_called_once_with(mock_state)

    def test_a_extends_left(self, window, mock_state):
        with patch("clipper.gui.main_window.extend_left") as mock:
            self._press(window, Qt.Key.Key_A, "a")
            mock.assert_called_once_with(mock_state)

    def test_i_marks_in(self, window, mock_state):
        with patch("clipper.gui.main_window.set_mark_in") as mock:
            self._press(window, Qt.Key.Key_I, "i")
            mock.assert_called_once_with(mock_state)

    def test_enter_starts_export(self, window, mock_state):
        with patch("clipper.gui.main_window.start_export_job") as mock:
            self._press(window, Qt.Key.Key_Return)
            mock.assert_called_once_with(mock_state)
