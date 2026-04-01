from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

from clipper.exit_prompt import (
    cycle_exit_prompt_focus,
    finish_exit_prompt_action,
    queue_exit_prompt_action,
    request_exit,
    show_exit_prompt,
)
from clipper.controls import handle_key

from tests.test_clipper_state import _make_state


class TestHandleKey:
    def test_space_toggles_loop_pause(self):
        state = _make_state()
        handle_key(state, 32)
        assert state.loop_paused is True
        handle_key(state, 32)
        assert state.loop_paused is False

    def test_zero_accepts_suggested_out(self):
        state = _make_state(active_start=10, active_end=30, initial_active_start=0, initial_active_end=30)
        state.suggested_out = 24
        handle_key(state, ord("0"))
        assert state.active_end == 24

    def test_nine_accepts_suggested_in(self):
        state = _make_state(active_start=10, active_end=30, initial_active_start=10, initial_active_end=79)
        state.suggested_in = 14
        handle_key(state, ord("9"))
        assert state.active_start == 14

    def test_l_cycles_loop_mode(self):
        state = _make_state(loop_mode="base-tip-base")
        handle_key(state, ord("l"))
        assert state.loop_mode == "tip-base-tip"

    def test_comma_shifts_active_range_left(self):
        state = _make_state(active_start=20, active_end=30, current=25)
        handle_key(state, ord(","))
        assert state.active_start == 10
        assert state.active_end == 20

    def test_period_shifts_active_range_right(self):
        state = _make_state(active_start=10, active_end=20, current=15)
        handle_key(state, ord("."))
        assert state.active_start == 20
        assert state.active_end == 30

    def test_a_extends_loaded_left(self):
        state = _make_state(loaded_start=10, active_start=20, base_step=5)
        with patch("clipper.loaded_bounds.ensure_loaded") as ensure_loaded:
            ensure_loaded.side_effect = lambda s, want_start, _want_end: setattr(s, "loaded_start", want_start)
            handle_key(state, ord("a"))
        assert state.loaded_start == 5

    def test_s_contracts_loaded_left(self):
        state = _make_state(loaded_start=10, active_start=20, base_step=5)
        handle_key(state, ord("s"))
        assert state.loaded_start == 15

    def test_d_contracts_loaded_right(self):
        state = _make_state(loaded_end=40, active_end=30, base_step=5)
        handle_key(state, ord("d"))
        assert state.loaded_end == 35

    def test_f_extends_loaded_right(self):
        state = _make_state(loaded_end=30, active_end=20, total_frames=50, base_step=5)
        with patch("clipper.loaded_bounds.ensure_loaded") as ensure_loaded:
            ensure_loaded.side_effect = lambda s, _want_start, want_end: setattr(s, "loaded_end", want_end)
            handle_key(state, ord("f"))
        assert state.loaded_end == 35


class TestExitPromptControls:
    def test_show_exit_prompt_defaults_focus_to_save(self):
        state = _make_state()
        state.exit_prompt_focus = "wat"

        show_exit_prompt(state)

        assert state.exit_prompt_visible is True
        assert state.exit_prompt_focus == "save"
        assert state.exit_prompt_action == ""

    def test_cycle_exit_prompt_focus_uses_tab_order(self):
        state = _make_state()
        show_exit_prompt(state)

        cycle_exit_prompt_focus(state)
        assert state.exit_prompt_focus == "discard"
        cycle_exit_prompt_focus(state)
        assert state.exit_prompt_focus == "cancel"
        cycle_exit_prompt_focus(state)
        assert state.exit_prompt_focus == "save"

    def test_queue_exit_prompt_action_uses_current_focus_for_enter(self):
        state = _make_state()
        state.exit_prompt_focus = "discard"

        queue_exit_prompt_action(state)

        assert state.exit_prompt_action == "discard"

    def test_queue_exit_prompt_action_can_force_cancel(self):
        state = _make_state()
        state.exit_prompt_focus = "discard"

        queue_exit_prompt_action(state, "cancel")

        assert state.exit_prompt_focus == "cancel"
        assert state.exit_prompt_action == "cancel"

    def test_finish_exit_prompt_action_cancels_without_exiting(self):
        state = _make_state()
        state.exit_prompt_visible = True
        state.exit_prompt_focus = "discard"
        state.exit_prompt_action = "discard"
        state.render_rev = 0

        result = finish_exit_prompt_action(state, "cancel")

        assert result is False
        assert state.exit_prompt_visible is False
        assert state.exit_prompt_focus == "save"
        assert state.exit_prompt_action == ""
        assert state.render_rev == 1

    def test_finish_exit_prompt_action_restores_original_session_for_discard(self):
        state = _make_state()
        state.exit_prompt_visible = True

        with patch("clipper.exit_prompt.restore_original_session") as restore:
            result = finish_exit_prompt_action(state, "discard")

        assert result is True
        restore.assert_called_once_with(state)
        assert state.exit_prompt_visible is False
        assert state.exit_prompt_focus == "save"
        assert state.exit_prompt_action == ""

    def test_request_exit_autosaves_for_dirty_new_session(self):
        state = _make_state()
        state.dirty = True
        state.autosave_session = MagicMock()

        result = request_exit(state)

        assert result is True
        state.autosave_session.assert_called_once_with()

    def test_request_exit_shows_prompt_for_dirty_existing_session(self):
        state = _make_state()
        state.dirty = True
        state.protect_existing_save_data = True
        state.autosave_session = MagicMock()

        result = request_exit(state)

        assert result is False
        assert state.exit_prompt_visible is True
        state.autosave_session.assert_not_called()


