"""Tests for clipper.gui.launcher_dialog — session launcher dialog."""

from __future__ import annotations

from pathlib import PureWindowsPath

import pytest
from PyQt6.QtWidgets import QApplication

from clipper.content import load_content
from clipper.gui import launcher_dialog
from clipper.gui.launcher_dialog import VR_VIDEO_DIR, LauncherDialog


@pytest.fixture()
def dialog():
    return LauncherDialog()


class TestClipWholeButton:
    def test_clip_whole_button_exists(self, dialog):
        assert hasattr(dialog, "clip_whole_btn")
        assert dialog.clip_whole_btn.text() == "Clip whole vid..."

    def test_build_result_clip_whole_mode(self, dialog):
        dialog._clip_whole_file = "/path/to/loop.mp4"
        result = dialog.build_result()
        assert result == {
            "ok": True,
            "mode": "clip_whole",
            "video_file": "/path/to/loop.mp4",
        }

    def test_build_result_prefers_clip_whole_over_radio(self, dialog):
        """When _clip_whole_file is set, mode is clip_whole regardless of radio."""
        dialog.new_radio.setChecked(True)
        dialog._clip_whole_file = "/path/to/loop.mp4"
        result = dialog.build_result()
        assert result["mode"] == "clip_whole"


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
    """Which folder a clip lands in -- CLIPS_DIR or VR_CLIPS_DIR -- is decided here.

    Both cases used to build their input out of ``VR_VIDEO_DIR`` itself, so the
    assertion held for any value of it: repointing the constant at a folder that
    is not in the library left both green while every VR clip silently routed to
    the non-VR folder.  The paths below are literals in the two spellings the
    file dialog returns, against a fabricated root.
    """

    VR_DIR = PureWindowsPath(r"D:\example-suite") / "videos" / "videos" / "VR"

    @pytest.fixture(autouse=True)
    def _fabricated_library(self, monkeypatch):
        monkeypatch.setattr(launcher_dialog, "VR_VIDEO_DIR", self.VR_DIR)

    @pytest.mark.parametrize("typed, is_vr", [
        (r"D:\example-suite\videos\videos\VR\seaside walk.mp4", True),
        ("D:/example-suite/videos/videos/VR/seaside walk.mp4", True),
        (r"D:\example-suite\videos\videos\VR\second pass\seaside walk.mp4", True),
        (r"D:\example-suite\videos\videos\flat\seaside walk.mp4", False),
        (r"D:\example-suite\videos\videos\VR-favourites\seaside walk.mp4", False),
        (r"D:\example-suite\videos\VR\seaside walk.mp4", False),
        (r"E:\example-suite\videos\videos\VR\seaside walk.mp4", False),
        ("", False),
    ])
    def test_the_vr_box_follows_the_folder_the_file_sits_in(self, dialog, typed, is_vr):
        dialog.video_file_edit.setText(typed)

        assert dialog.vr_checkbox.isChecked() is is_vr

    def test_choosing_a_non_vr_file_after_a_vr_one_clears_the_box(self, dialog):
        dialog.video_file_edit.setText(r"D:\example-suite\videos\videos\VR\seaside walk.mp4")

        dialog.video_file_edit.setText(r"D:\example-suite\videos\videos\flat\seaside walk.mp4")

        assert dialog.vr_checkbox.isChecked() is False


class TestVrVideoDir:
    def test_it_is_the_vr_folder_under_the_librarys_own_root(self):
        """The literal tail is written here, so repointing the constant reds this."""
        assert VR_VIDEO_DIR.parts[-3:] == ("videos", "videos", "VR")

        suite_root = PureWindowsPath(load_content()["suite_root"])
        assert VR_VIDEO_DIR.is_relative_to(suite_root)
