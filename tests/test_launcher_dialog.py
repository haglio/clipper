"""Tests for clipper.gui.launcher_dialog — session launcher dialog."""

from __future__ import annotations

from pathlib import PureWindowsPath
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QFileDialog

from clipper.content import load_content
from clipper.gui import launcher_dialog
from clipper.gui.launcher_dialog import VR_VIDEO_DIR, LauncherDialog
from clipper.launch_choice import ClipWholeVideo, LoadSession, NewSession


@pytest.fixture
def dialog():
    return LauncherDialog()


def _choose_file(dialog, path: str) -> None:
    """Click "Clip whole vid..." and have the file chooser answer with `path`."""
    with patch.object(QFileDialog, "getOpenFileName", return_value=(path, "")):
        dialog.clip_whole_btn.click()


class TestClipWholeButton:
    def test_clip_whole_button_exists(self, dialog):
        assert hasattr(dialog, "clip_whole_btn")
        assert dialog.clip_whole_btn.text() == "Clip whole vid..."

    def test_picking_a_whole_video_returns_it_in_clip_whole_mode(self, dialog):
        _choose_file(dialog, r"D:\example-suite\videos\videos\seaside walk.mp4")

        assert dialog.build_result() == ClipWholeVideo(
            video_file=r"D:\example-suite\videos\videos\seaside walk.mp4"
        )

    def test_a_chosen_whole_video_wins_over_the_selected_radio(self, dialog):
        dialog.new_radio.setChecked(True)

        _choose_file(dialog, r"D:\example-suite\videos\videos\seaside walk.mp4")

        assert isinstance(dialog.build_result(), ClipWholeVideo)

    def test_canceling_the_chooser_leaves_the_dialog_in_its_normal_mode(self, dialog):
        dialog.load_radio.setChecked(True)

        _choose_file(dialog, "")

        assert isinstance(dialog.build_result(), LoadSession)


class TestResult:
    def test_the_load_radio_asks_for_the_session_file_named_beside_it(self, dialog):
        dialog.load_radio.setChecked(True)
        dialog.session_json_edit.setText("/path/to/session.json")

        assert dialog.build_result() == LoadSession(session_json="/path/to/session.json")

    def test_the_new_radio_asks_for_the_form_the_user_filled_in(self, dialog):
        dialog.new_radio.setChecked(True)
        dialog.session_name_edit.setText("my_clip")
        dialog.video_file_edit.setText("/path/to/video.mp4")
        dialog.timestamp_edit.setText("00:01:30")
        dialog.seconds_edit.setText("5")

        assert dialog.build_result() == NewSession(
            video_file="/path/to/video.mp4",
            session_name="my_clip",
            timestamp="00:01:30",
            seconds=5.0,
            loop_mode=dialog.loop_mode_combo.currentText(),
            vr=False,
        )

    def test_build_result_new_mode_vr_default_false(self, dialog):
        dialog.new_radio.setChecked(True)
        dialog.video_file_edit.setText("/path/to/video.mp4")

        assert dialog.build_result().vr is False

    def test_build_result_new_mode_vr_checked(self, dialog):
        dialog.new_radio.setChecked(True)
        dialog.vr_checkbox.setChecked(True)

        assert dialog.build_result().vr is True

    def test_prefilling_fills_the_new_session_form_and_selects_it(self, dialog):
        dialog.load_radio.setChecked(True)

        dialog.prefill("beta rehearsal", "D:/media/example/beta rehearsal.mp4",
                       "00:01:35.250")

        assert dialog.build_result() == NewSession(
            video_file="D:/media/example/beta rehearsal.mp4",
            session_name="beta rehearsal",
            timestamp="00:01:35.250",
            seconds=5.0,
            loop_mode=dialog.loop_mode_combo.currentText(),
            vr=False,
        )


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
        (r"D:\example-suite\videos\videos\VR-favorites\seaside walk.mp4", False),
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
