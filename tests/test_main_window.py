"""Tests for clipper.gui.main_window — main application window."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from clipper.gui.main_window import ClipperMainWindow, _WrapRow
from clipper.state import ExportJob


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
        assert window.windowTitle() == "Clipper"

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


# The state every dispatch case starts from: room on both sides of the loaded
# range to contract into, and room outside it to extend into.
_DISPATCH_STATE = {
    "total_frames": 100, "loaded_start": 10, "loaded_end": 60,
    "active_start": 20, "active_end": 40, "current": 30, "base_step": 5,
}


def _press(window, key, text=""):
    window.keyPressEvent(
        QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, text)
    )


def _no_prep(state):
    pass


def _with_suggestions(state):
    state.suggested_in = 25
    state.suggested_out = 35


def _with_an_export_running(state):
    state.export_job = ExportJob()


# (label, Qt key, event text, prepare, what to read afterwards, what it must be)
# -- every branch of keyPressEvent, read off a real VideoState.  Six of these
# used to be `patch(...); assert_called_once_with(state)`, which pins the
# import name rather than the edit: swapping the handlers behind s/d and w/l,
# and flipping the sign of both change_speed steps, shipped green.
def _dispatched_tokens() -> set[str]:
    """Every literal ``keyPressEvent`` branches on, read off its syntax tree."""
    import ast
    import inspect
    import textwrap

    from clipper.gui import main_window

    tree = ast.parse(
        textwrap.dedent(inspect.getsource(main_window.ClipperMainWindow.keyPressEvent))
    )
    tokens: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for operand in node.comparators:
            for leaf in ast.walk(operand):
                if isinstance(leaf, ast.Constant) and isinstance(leaf.value, str):
                    tokens.add(leaf.value)
                elif isinstance(leaf, ast.Attribute) and leaf.attr.startswith("Key_"):
                    tokens.add(leaf.attr)
    return tokens


_KEY_BINDINGS = [
    ("left", Qt.Key.Key_Left, "", _no_prep, lambda s: s.current, 29),
    ("right", Qt.Key.Key_Right, "", _no_prep, lambda s: s.current, 31),
    ("space", Qt.Key.Key_Space, "", _no_prep, lambda s: s.loop_paused, True),
    ("a extends left", Qt.Key.Key_A, "a", _no_prep, lambda s: s.loaded_start, 5),
    ("s contracts left", Qt.Key.Key_S, "s", _no_prep, lambda s: s.loaded_start, 15),
    ("d contracts right", Qt.Key.Key_D, "d", _no_prep, lambda s: s.loaded_end, 55),
    ("f extends right", Qt.Key.Key_F, "f", _no_prep, lambda s: s.loaded_end, 65),
    ("i marks in", Qt.Key.Key_I, "i", _no_prep, lambda s: s.active_start, 30),
    ("[ marks in", Qt.Key.Key_BracketLeft, "[", _no_prep, lambda s: s.active_start, 30),
    ("o marks out", Qt.Key.Key_O, "o", _no_prep, lambda s: s.active_end, 30),
    ("] marks out", Qt.Key.Key_BracketRight, "]", _no_prep, lambda s: s.active_end, 30),
    ("9 accepts the suggested in", Qt.Key.Key_9, "9", _with_suggestions, lambda s: s.active_start, 25),
    ("( accepts the suggested in", Qt.Key.Key_ParenLeft, "(", _with_suggestions, lambda s: s.active_start, 25),
    ("0 accepts the suggested out", Qt.Key.Key_0, "0", _with_suggestions, lambda s: s.active_end, 35),
    (") accepts the suggested out", Qt.Key.Key_ParenRight, ")", _with_suggestions, lambda s: s.active_end, 35),
    (", shifts left", Qt.Key.Key_Comma, ",", _no_prep, lambda s: (s.active_start, s.active_end), (0, 20)),
    ("< shifts left", Qt.Key.Key_Less, "<", _no_prep, lambda s: (s.active_start, s.active_end), (0, 20)),
    (". shifts right", Qt.Key.Key_Period, ".", _no_prep, lambda s: (s.active_start, s.active_end), (40, 60)),
    ("> shifts right", Qt.Key.Key_Greater, ">", _no_prep, lambda s: (s.active_start, s.active_end), (40, 60)),
    ("w toggles the wrap range", Qt.Key.Key_W, "w", _no_prep, lambda s: s.wrap_mode, "yellow"),
    ("l cycles the loop mode", Qt.Key.Key_L, "l", _no_prep, lambda s: s.loop_mode, "tip-base-tip"),
    ("- slows down", Qt.Key.Key_Minus, "-", _no_prep, lambda s: s.speed, 0.75),
    ("_ slows down", Qt.Key.Key_Underscore, "_", _no_prep, lambda s: s.speed, 0.75),
    ("+ speeds up", Qt.Key.Key_Plus, "+", _no_prep, lambda s: s.speed, 1.25),
    ("= speeds up", Qt.Key.Key_Equal, "=", _no_prep, lambda s: s.speed, 1.25),
    ("escape dismisses the export", Qt.Key.Key_Escape, "", _with_an_export_running,
     lambda s: s.export_job.dismissed, True),
]


class TestKeyDispatch:
    """Every keyboard binding, against a real VideoState."""

    @pytest.mark.parametrize(
        "key, text, prepare, observe, expected",
        [pytest.param(k, t, p, o, e, id=label) for label, k, t, p, o, e in _KEY_BINDINGS],
    )
    def test_a_key_makes_its_edit(self, make_state, key, text, prepare, observe, expected):
        state = make_state(**_DISPATCH_STATE)
        prepare(state)
        window = ClipperMainWindow(state)

        _press(window, key, text)

        assert observe(state) == expected

    def test_every_binding_the_window_dispatches_has_a_row(self):
        """A binding added to keyPressEvent without a case here fails this.

        Fourteen of the twenty went unpinned for exactly as long as nothing
        counted them.
        """
        covered = {"Key_Return", "Key_Enter", "q"}  # the three cases below
        covered |= {text or key.name for _, key, text, *_ in _KEY_BINDINGS}

        assert _dispatched_tokens() == covered

    def test_an_unbound_key_changes_nothing(self, make_state):
        state = make_state(**_DISPATCH_STATE)
        window = ClipperMainWindow(state)
        before = (state.current, state.active_start, state.active_end,
                  state.loaded_start, state.loaded_end, state.wrap_mode,
                  state.loop_mode, state.speed, state.dirty)

        _press(window, Qt.Key.Key_Z, "z")

        assert (state.current, state.active_start, state.active_end,
                state.loaded_start, state.loaded_end, state.wrap_mode,
                state.loop_mode, state.speed, state.dirty) == before

    @pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
    def test_enter_starts_an_export(self, make_state, key):
        state = make_state(**_DISPATCH_STATE)
        window = ClipperMainWindow(state)

        with patch("clipper.gui.main_window.ExportWorker") as worker_cls, \
             patch("clipper.gui.main_window.ExportDialog") as dialog_cls:
            _press(window, key)

        dialog_cls.return_value.show.assert_called_once()
        worker_cls.return_value.start.assert_called_once()

    def test_escape_leaves_an_already_dismissed_export_alone(self, make_state):
        state = make_state(**_DISPATCH_STATE)
        state.export_job = ExportJob(dismissed=True, stage="fixing")
        window = ClipperMainWindow(state)

        _press(window, Qt.Key.Key_Escape)

        assert state.export_job.stage == "fixing"

    def test_q_closes_the_window(self, make_state):
        state = make_state(**_DISPATCH_STATE)
        window = ClipperMainWindow(state)
        window.show()
        assert window.isVisible()

        _press(window, Qt.Key.Key_Q, "q")

        assert not window.isVisible()


def _brace_ink(row, rendered) -> list[int]:
    """The x columns the wrap brace paints, read off the row it is drawn on."""
    image = rendered(row)
    background = image.pixelColor(row.width() - 2, 1).name()
    mid = row.height() // 2
    return [x for x in range(row.width()) if image.pixelColor(x, mid).name() != background]


def _brace_width(window, rendered) -> int:
    ink = _brace_ink(window.findChild(_WrapRow), rendered)
    return (max(ink) - min(ink)) if ink else 0


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

    def test_wrap_brace_spans_loaded_range_in_blue_mode(self, shown_window, mock_state, rendered):
        w = shown_window
        mock_state.wrap_mode = "blue"
        mock_state.loaded_start = 0
        mock_state.loaded_end = 100
        w.timeline.set_loaded_range(0, 100)
        QApplication.processEvents()
        w.update_button_positions()

        # Brace should span full timeline width (loaded range)
        assert _brace_width(w, rendered) > w.timeline.width() * 0.8

    def test_wrap_brace_narrows_to_active_range_in_yellow_mode(self, shown_window, mock_state, rendered):
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
        brace_width = _brace_width(w, rendered)
        assert brace_width < w.timeline.width() * 0.4


class TestWrapBrace:
    """The brace under the timeline showing what the cursor wraps within."""

    def test_it_draws_a_line_across_exactly_the_span_it_was_given(self, rendered):
        row = _WrapRow()
        row.resize(600, 30)

        row.set_brace(100, 400)

        ink = _brace_ink(row, rendered)
        assert (min(ink), max(ink)) == (100, 400)

    def test_an_empty_span_draws_nothing(self, rendered):
        row = _WrapRow()
        row.resize(600, 30)

        row.set_brace(300, 300)

        assert _brace_ink(row, rendered) == []
