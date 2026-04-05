"""Tests for clipper.gui.video_pane — video frame display widget."""

from __future__ import annotations

import sys
from unittest.mock import patch

import numpy as np
import pytest
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

from clipper.gui.frame_converter import bgr_to_qimage
from clipper.gui.video_pane import VideoPane


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def pane():
    return VideoPane()


@pytest.fixture()
def sample_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (50, 100, 150)  # BGR
    return frame


class TestConstruction:
    def test_minimum_size_set(self, pane):
        assert pane.minimumWidth() >= 320
        assert pane.minimumHeight() >= 240

    def test_initial_frame_is_none(self, pane):
        assert pane._image is None


class TestSetFrame:
    def test_set_frame_stores_image(self, pane, sample_frame):
        qimg = bgr_to_qimage(sample_frame)
        pane.set_frame(qimg)
        assert pane._image is not None
        assert pane._image.width() == 640

    def test_set_frame_triggers_update(self, pane, sample_frame):
        qimg = bgr_to_qimage(sample_frame)
        with patch.object(pane, "update") as mock_update:
            pane.set_frame(qimg)
            mock_update.assert_called_once()

    def test_clear_frame(self, pane, sample_frame):
        qimg = bgr_to_qimage(sample_frame)
        pane.set_frame(qimg)
        pane.set_frame(None)
        assert pane._image is None
