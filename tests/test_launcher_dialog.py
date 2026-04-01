"""Tests for clipper.gui.launcher_dialog — session launcher dialog."""

from __future__ import annotations

import sys

import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.launcher_dialog import LauncherDialog


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def dialog():
    return LauncherDialog()


class TestConstruction:
    def test_has_mode_radios(self, dialog):
        assert dialog.load_radio is not None
        assert dialog.new_radio is not None

    def test_default_mode(self, dialog):
        # One of them should be checked
        assert dialog.load_radio.isChecked() or dialog.new_radio.isChecked()

    def test_has_session_field(self, dialog):
        assert dialog.session_json_edit is not None

    def test_has_new_session_fields(self, dialog):
        assert dialog.session_name_edit is not None
        assert dialog.video_file_edit is not None
        assert dialog.timestamp_edit is not None
        assert dialog.seconds_edit is not None
        assert dialog.loop_mode_combo is not None


class TestResult:
    def test_build_result_load_mode(self, dialog):
        dialog.load_radio.setChecked(True)
        dialog.session_json_edit.setText("/path/to/session.json")
        result = dialog.build_result()
        assert result["mode"] == "load"
        assert result["session_json"] == "/path/to/session.json"
        assert result["ok"] is True

    def test_build_result_new_mode(self, dialog):
        dialog.new_radio.setChecked(True)
        dialog.session_name_edit.setText("my_clip")
        dialog.video_file_edit.setText("/path/to/video.mp4")
        dialog.timestamp_edit.setText("00:01:30")
        dialog.seconds_edit.setText("5")
        result = dialog.build_result()
        assert result["mode"] == "new"
        assert result["session_name"] == "my_clip"
        assert result["video_file"] == "/path/to/video.mp4"
        assert result["timestamp"] == "00:01:30"
        assert result["seconds"] == 5.0
        assert result["ok"] is True

    def test_build_result_includes_loop_mode(self, dialog):
        dialog.new_radio.setChecked(True)
        dialog.session_name_edit.setText("test")
        dialog.video_file_edit.setText("/video.mp4")
        dialog.timestamp_edit.setText("00:00:00")
        dialog.seconds_edit.setText("3")
        result = dialog.build_result()
        assert "loop_mode" in result
