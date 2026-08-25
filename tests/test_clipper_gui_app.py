"""Tests for clipper.gui.app — application wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from shared_ui.colors import BG_SECONDARY

from clipper.gui.app import ClipperApp


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
    state.render_rev = 0
    return state


class TestConstruction:
    def test_creates_main_window(self, mock_state):
        app = ClipperApp(mock_state)
        assert app.window is not None

    def test_creates_playback_timer(self, mock_state):
        app = ClipperApp(mock_state)
        assert app.playback_timer is not None

    def test_the_window_is_built_around_the_state_it_was_given(self, mock_state):
        app = ClipperApp(mock_state)
        assert app.window.session_label.text() == mock_state.session_name

    def test_sets_application_icon(self, mock_state):
        ClipperApp(mock_state)

        assert not QApplication.instance().windowIcon().isNull()


# The state _on_tick is driven against: a real one, with frames it can decode.
_TICK_STATE = {
    "total_frames": 100, "loaded_start": 10, "loaded_end": 60,
    "active_start": 20, "active_end": 40, "current": 33, "base_step": 5,
    "fps": 25.0,
}


@pytest.fixture()
def live_app(make_state):
    """A ClipperApp over a real VideoState, with visible frames to draw."""
    state = make_state(**_TICK_STATE)
    for idx in state.frames:
        state.frames[idx] = np.full((8, 8, 3), 200, dtype=np.uint8)
    app = ClipperApp(state)
    app.window.resize(1520, 960)
    yield app
    app.playback_timer.stop()
    app.window.close()


def _is_blank(pane, rendered) -> bool:
    image = rendered(pane)
    return all(
        image.pixelColor(x, y).name() == BG_SECONDARY.name()
        for x in range(0, image.width(), 7)
        for y in range(0, image.height(), 7)
    )


class TestOnTick:
    """The whole visible application, sixty times a second.

    Nothing exercised it: making it feed the timeline zeros instead of reading
    the state left the whole suite at baseline, and gui/app.py sat at 30%
    covered with 51 of its 73 statements never run.
    """

    def test_it_hands_the_timeline_the_state_it_is_looking_at(self, live_app):
        state = live_app._state

        live_app._on_tick()

        timeline = live_app.window.timeline
        assert (timeline.loaded_start, timeline.loaded_end) == (10, 60)
        assert (timeline.active_start, timeline.active_end) == (20, 40)
        assert timeline.cursor_pos == 33
        assert state.active_start <= timeline.loop_pos <= state.active_end
        assert timeline.wrap_mode == "blue"

    def test_it_follows_the_state_when_it_moves(self, live_app):
        live_app._on_tick()
        live_app._state.current = 47
        live_app._state.active_end = 50
        live_app._state.wrap_mode = "yellow"

        live_app._on_tick()

        timeline = live_app.window.timeline
        assert timeline.cursor_pos == 47
        assert timeline.active_end == 50
        assert timeline.wrap_mode == "yellow"

    def test_it_passes_the_suggestions_through(self, live_app):
        live_app._state.suggested_in = 22
        live_app._state.suggested_out = 38

        live_app._on_tick()

        timeline = live_app.window.timeline
        assert (timeline.suggested_in, timeline.suggested_out) == (22, 38)

    def test_it_puts_a_frame_in_both_panes(self, live_app, rendered):
        window = live_app.window
        assert _is_blank(window.left_pane, rendered)
        assert _is_blank(window.right_pane, rendered)

        live_app._on_tick()

        assert not _is_blank(window.left_pane, rendered)
        assert not _is_blank(window.right_pane, rendered)

    def test_it_writes_the_cursor_position_and_timestamp(self, live_app):
        live_app._on_tick()

        # frame 33 is the 23rd of the 51 loaded, at 25 fps
        assert live_app.window.cursor_label.text() == "cursor: 23/50 @ 00:00:01.320"

    def test_it_writes_the_loop_length_and_the_speed(self, live_app):
        live_app._state.speed = 1.5

        live_app._on_tick()

        assert "/21 @ " in live_app.window.loop_label.text()
        assert live_app.window.speed_label.text() == "speed: 1.50x (playing)"

    def test_a_paused_loop_says_so(self, live_app):
        live_app._state.loop_paused = True

        live_app._on_tick()

        assert live_app.window.speed_label.text() == "speed: 1.00x (paused)"

    def test_it_shows_the_session_warning_the_state_carries(self, live_app):
        live_app._state.session_warning = "Autosave failed: disk full"

        live_app._on_tick()

        assert live_app.window.warning_label.text() == "Autosave failed: disk full"

    def test_it_tells_the_controls_which_loop_mode_is_on(self, live_app):
        live_app._state.loop_mode = "tip-base"

        live_app._on_tick()

        assert live_app.window.timeline_controls.loop_mode_btn.text() == "tip-base"

    def test_a_frame_that_cannot_be_decoded_does_not_stop_the_rest(self, live_app):
        """The panes go without, but the timeline and labels still update."""
        with patch("clipper.frame_store.safe_frame", side_effect=KeyError("gone")):
            live_app._on_tick()

        assert live_app.window.timeline.cursor_pos == 33
        assert live_app.window.speed_label.text() == "speed: 1.00x (playing)"


class TestRun:
    def test_run_shows_the_window_and_starts_the_animation(self, live_app, ticked_within):
        with patch.object(QApplication, "exec", return_value=0) as event_loop:
            assert live_app.run() == 0

        event_loop.assert_called_once()
        assert live_app.window.isVisible()
        assert ticked_within(live_app.playback_timer.tick, 2000) is True

    def test_the_tick_is_wired_to_the_frame_update(self, live_app, ticked_within):
        with patch.object(QApplication, "exec", return_value=0):
            live_app.run()

        assert ticked_within(live_app.playback_timer.tick, 2000) is True
        assert live_app.window.timeline.cursor_pos == 33
