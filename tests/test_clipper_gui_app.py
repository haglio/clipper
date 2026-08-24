"""Tests for clipper.gui.app — application wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication

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

    def test_window_has_state(self, mock_state):
        app = ClipperApp(mock_state)
        assert app.window._state is mock_state

    def test_sets_application_icon(self, mock_state):
        app = ClipperApp(mock_state)
        qapp = QApplication.instance()
        assert not qapp.windowIcon().isNull()
