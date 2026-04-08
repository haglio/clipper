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

    def test_build_result_new_mode_vr_default_false(self, dialog):
        dialog.new_radio.setChecked(True)
        dialog.video_file_edit.setText("/path/to/video.mp4")
        result = dialog.build_result()
        assert result["vr"] is False

    def test_build_result_new_mode_vr_checked(self, dialog):
        dialog.new_radio.setChecked(True)
        dialog.vr_checkbox.setChecked(True)
        result = dialog.build_result()
        assert result["vr"] is True


class TestVrAutoDetect:
    def test_vr_prechecked_for_vr_path(self):
        dialog = LauncherDialog()
        dialog.new_radio.setChecked(True)
        dialog.video_file_edit.setText(r"C:\path\to\suite-root\videos\videos\VR\some_video.mp4")
        dialog._on_video_path_changed()
        assert dialog.vr_checkbox.isChecked() is True

    def test_vr_not_prechecked_for_non_vr_path(self):
        dialog = LauncherDialog()
        dialog.new_radio.setChecked(True)
        dialog.video_file_edit.setText(r"C:\path\to\suite-root\videos\videos\other\some_video.mp4")
        dialog._on_video_path_changed()
        assert dialog.vr_checkbox.isChecked() is False
