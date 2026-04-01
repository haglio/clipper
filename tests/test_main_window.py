"""Tests for clipper.gui.main_window — main application window."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QPoint, Qt
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

    def test_all_buttons_have_no_focus_policy(self, window):
        """Buttons must not steal focus — arrow/space/enter must reach keyPressEvent."""
        from PyQt6.QtWidgets import QPushButton

        buttons = window.findChildren(QPushButton)
        assert len(buttons) > 0
        for btn in buttons:
            assert btn.focusPolicy() == Qt.FocusPolicy.NoFocus, (
                f"Button '{btn.text()}' has focus policy {btn.focusPolicy()}, expected NoFocus"
            )


class TestCloseEvent:
    def test_close_accepted_when_no_prompt_needed(self, window, mock_state):
        mock_state.should_prompt_on_exit = False
        from PyQt6.QtGui import QCloseEvent

        event = QCloseEvent()
        window.closeEvent(event)
        assert event.isAccepted()

    def _make_exit_dialog_mock(self, choice):
        from clipper.gui.exit_dialog import ExitDialog

        mock_cls = MagicMock()
        mock_cls.SAVE = ExitDialog.SAVE
        mock_cls.DISCARD = ExitDialog.DISCARD
        mock_cls.CANCEL = ExitDialog.CANCEL
        mock_dialog = MagicMock()
        mock_dialog.choice = choice
        mock_cls.return_value = mock_dialog
        return mock_cls

    def test_close_saves_and_accepts_on_save_choice(self, window, mock_state):
        mock_state.should_prompt_on_exit = True
        from PyQt6.QtGui import QCloseEvent
        from clipper.gui.exit_dialog import ExitDialog

        mock_cls = self._make_exit_dialog_mock(ExitDialog.SAVE)

        with patch("clipper.gui.main_window.ExitDialog", mock_cls):
            event = QCloseEvent()
            window.closeEvent(event)

        mock_state.autosave_session.assert_called_once()
        assert event.isAccepted()

    def test_close_ignores_on_cancel_choice(self, window, mock_state):
        mock_state.should_prompt_on_exit = True
        from PyQt6.QtGui import QCloseEvent
        from clipper.gui.exit_dialog import ExitDialog

        mock_cls = self._make_exit_dialog_mock(ExitDialog.CANCEL)

        with patch("clipper.gui.main_window.ExitDialog", mock_cls):
            event = QCloseEvent()
            window.closeEvent(event)

        mock_state.autosave_session.assert_not_called()
        assert not event.isAccepted()

    def test_close_discards_without_saving(self, window, mock_state):
        mock_state.should_prompt_on_exit = True
        from PyQt6.QtGui import QCloseEvent
        from clipper.gui.exit_dialog import ExitDialog

        mock_cls = self._make_exit_dialog_mock(ExitDialog.DISCARD)

        with patch("clipper.gui.main_window.ExitDialog", mock_cls):
            event = QCloseEvent()
            window.closeEvent(event)

        mock_state.autosave_session.assert_not_called()
        assert event.isAccepted()


class TestExportWiring:
    def test_export_creates_dialog_and_worker(self, window, mock_state):
        mock_worker = MagicMock()
        mock_dialog = MagicMock()

        with patch("clipper.gui.main_window.ExportWorker", return_value=mock_worker) as MockWorker, \
             patch("clipper.gui.main_window.ExportDialog", return_value=mock_dialog) as MockDialog:
            window._on_export()

        MockDialog.assert_called_once_with(window)
        MockWorker.assert_called_once_with(mock_state)
        mock_dialog.show.assert_called_once()
        mock_worker.start.assert_called_once()


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

    def test_enter_triggers_export(self, window, mock_state):
        with patch.object(window, "_on_export") as mock:
            self._press(window, Qt.Key.Key_Return)
            mock.assert_called_once()


@pytest.fixture()
def shown_window(mock_state):
    """Window that has been shown so geometry is computed."""
    w = ClipperMainWindow(mock_state)
    w.resize(1520, 960)
    w.show()
    QApplication.processEvents()
    yield w
    w.close()


class TestDynamicPositioning:
    """Shift/mark/wrap buttons must track timeline positions each tick."""

    def test_shift_buttons_center_on_active_range(self, shown_window, mock_state):
        w = shown_window
        mock_state.active_start = 20
        mock_state.active_end = 80
        w.timeline.set_loaded_range(0, 100)
        w.timeline.set_active_range(20, 80)
        QApplication.processEvents()

        w.update_button_positions()

        tl = w.timeline
        tc = w.timeline_controls
        in_x = tl.mapToGlobal(QPoint(tl.x_for_index(20), 0)).x()
        out_x = tl.mapToGlobal(QPoint(tl.x_for_index(80), 0)).x()
        expected_center = (in_x + out_x) // 2

        left_global = tc.shift_left_btn.mapToGlobal(QPoint(tc.shift_left_btn.width(), 0)).x()
        right_global = tc.shift_right_btn.mapToGlobal(QPoint(0, 0)).x()
        actual_center = (left_global + right_global) // 2

        assert abs(actual_center - expected_center) < 10

    def test_shift_buttons_move_when_active_range_changes(self, shown_window, mock_state):
        w = shown_window
        tl = w.timeline
        tc = w.timeline_controls
        tl.set_loaded_range(0, 100)

        # Position with active range at left
        mock_state.active_start = 0
        mock_state.active_end = 20
        tl.set_active_range(0, 20)
        QApplication.processEvents()
        w.update_button_positions()
        left_pos = tc.shift_left_btn.mapToGlobal(QPoint(0, 0)).x()

        # Move active range to right
        mock_state.active_start = 60
        mock_state.active_end = 80
        tl.set_active_range(60, 80)
        QApplication.processEvents()
        w.update_button_positions()
        right_pos = tc.shift_left_btn.mapToGlobal(QPoint(0, 0)).x()

        assert right_pos > left_pos + 100

    def test_mark_buttons_straddle_cursor_inside_active(self, shown_window, mock_state):
        w = shown_window
        mock_state.active_start = 20
        mock_state.active_end = 80
        mock_state.current = 50
        w.timeline.set_loaded_range(0, 100)
        w.timeline.set_active_range(20, 80)
        QApplication.processEvents()
        w.update_button_positions()

        tc = w.timeline_controls
        in_right = tc.mark_in_btn.mapToGlobal(
            QPoint(tc.mark_in_btn.width(), 0)
        ).x()
        out_left = tc.mark_out_btn.mapToGlobal(QPoint(0, 0)).x()

        # [ ] should be adjacent (gap < 20px), with [ on the left
        assert out_left >= in_right
        assert out_left - in_right < 20

    def test_mark_buttons_split_when_cursor_outside_active(self, shown_window, mock_state):
        w = shown_window
        mock_state.active_start = 40
        mock_state.active_end = 60
        mock_state.current = 10  # left of active range
        w.timeline.set_loaded_range(0, 100)
        w.timeline.set_active_range(40, 60)
        QApplication.processEvents()
        w.update_button_positions()

        tc = w.timeline_controls
        # mark_in follows cursor (x=10), mark_out follows active_start (x=40)
        in_x = tc.mark_in_btn.mapToGlobal(QPoint(0, 0)).x()
        out_x = tc.mark_out_btn.mapToGlobal(QPoint(0, 0)).x()
        assert out_x > in_x + 50  # should be visibly separated

    def test_mark_in_disabled_at_active_end(self, shown_window, mock_state):
        w = shown_window
        mock_state.active_start = 20
        mock_state.active_end = 80
        mock_state.current = 80  # at active_end
        w.timeline.set_loaded_range(0, 100)
        QApplication.processEvents()
        w.update_button_positions()

        assert not w.timeline_controls.mark_in_btn.isEnabled()
        assert w.timeline_controls.mark_out_btn.isEnabled()

    def test_wrap_button_color_changes_with_mode(self, shown_window, mock_state):
        w = shown_window
        w.timeline.set_loaded_range(0, 100)
        w.timeline.set_active_range(20, 80)
        QApplication.processEvents()

        mock_state.wrap_mode = "blue"
        w.update_button_positions()
        blue_style = w.timeline_controls.wrap_btn.styleSheet()

        mock_state.wrap_mode = "yellow"
        w.update_button_positions()
        yellow_style = w.timeline_controls.wrap_btn.styleSheet()

        assert blue_style != yellow_style

    def test_wrap_brace_spans_loaded_range_in_blue_mode(self, shown_window, mock_state):
        w = shown_window
        mock_state.wrap_mode = "blue"
        mock_state.loaded_start = 0
        mock_state.loaded_end = 100
        w.timeline.set_loaded_range(0, 100)
        QApplication.processEvents()
        w.update_button_positions()

        # Brace should span full timeline width (loaded range)
        assert w._wrap_row._x2 - w._wrap_row._x1 > w.timeline.width() * 0.8

    def test_wrap_brace_narrows_to_active_range_in_yellow_mode(self, shown_window, mock_state):
        w = shown_window
        mock_state.wrap_mode = "yellow"
        mock_state.active_start = 40
        mock_state.active_end = 60
        mock_state.loaded_start = 0
        mock_state.loaded_end = 100
        w.timeline.set_loaded_range(0, 100)
        w.timeline.set_active_range(40, 60)
        QApplication.processEvents()
        w.update_button_positions()

        # Brace should be much narrower than timeline (only 20% of loaded range)
        brace_width = w._wrap_row._x2 - w._wrap_row._x1
        assert brace_width < w.timeline.width() * 0.4
