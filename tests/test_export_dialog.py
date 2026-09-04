"""Tests for clipper.gui.export_dialog — export progress dialog."""

from __future__ import annotations

import pytest

from clipper.gui.export_dialog import ExportDialog


@pytest.fixture
def dialog():
    return ExportDialog()


class TestConstruction:
    def test_has_three_progress_bars(self, dialog):
        assert dialog.clip_bar is not None
        assert dialog.fix_bar is not None
        assert dialog.audio_bar is not None

    def test_bars_start_at_zero(self, dialog):
        assert dialog.clip_bar.value() == 0
        assert dialog.fix_bar.value() == 0
        assert dialog.audio_bar.value() == 0


class TestProgressUpdates:
    def test_set_clip_progress(self, dialog):
        dialog.set_clip_progress(0.5)
        assert dialog.clip_bar.value() == 50

    def test_set_fix_progress(self, dialog):
        dialog.set_fix_progress(0.75)
        assert dialog.fix_bar.value() == 75

    def test_set_audio_progress(self, dialog):
        dialog.set_audio_progress(1.0)
        assert dialog.audio_bar.value() == 100


class TestStatusUpdates:
    def test_set_stage(self, dialog):
        dialog.set_stage("extracting audio")
        assert "audio" in dialog.stage_label.text().lower()

    def test_set_error(self, dialog):
        dialog.set_error("something broke")
        assert "broke" in dialog.error_label.text()

    def test_set_done(self, dialog):
        dialog.set_done(True)
        assert dialog.close_btn.isEnabled()
