"""Tests for clipper.gui.export_worker — QThread-based export."""

from __future__ import annotations

import sys

import pytest
from PyQt6.QtWidgets import QApplication

from clipper.gui.export_worker import ExportWorker


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestConstruction:
    def test_has_signals(self):
        worker = ExportWorker.__dict__
        # Verify signals are defined on the class
        assert "stage_changed" in worker
        assert "clip_progress" in worker
        assert "fix_progress" in worker
        assert "audio_progress" in worker
        assert "export_finished" in worker
