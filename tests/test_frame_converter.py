"""Tests for clipper.gui.frame_converter — BGR numpy array to QImage."""

from __future__ import annotations


import numpy as np
from PyQt6.QtGui import QImage

from clipper.gui.frame_converter import bgr_to_qimage, scale_to_fit


class TestBgrToQImage:
    def test_dimensions_match(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = bgr_to_qimage(frame)
        assert result.width() == 640
        assert result.height() == 480

    def test_bgr_to_rgb_swap(self):
        """A frame with BGR (255, 0, 0) = pure blue should become RGB blue."""
        frame = np.zeros((1, 1, 3), dtype=np.uint8)
        frame[0, 0] = (255, 0, 0)  # BGR: blue=255, green=0, red=0
        result = bgr_to_qimage(frame)
        pixel = result.pixelColor(0, 0)
        assert pixel.red() == 0
        assert pixel.green() == 0
        assert pixel.blue() == 255

    def test_rgb_preserved_for_grays(self):
        frame = np.full((1, 1, 3), 128, dtype=np.uint8)
        result = bgr_to_qimage(frame)
        pixel = result.pixelColor(0, 0)
        assert pixel.red() == 128
        assert pixel.green() == 128
        assert pixel.blue() == 128

    def test_survives_source_deletion(self):
        """QImage must own its data — not reference the numpy buffer."""
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        frame[:] = (50, 100, 150)  # BGR
        result = bgr_to_qimage(frame)
        del frame  # destroy source
        pixel = result.pixelColor(0, 0)
        # RGB should be (150, 100, 50) after BGR→RGB swap
        assert pixel.red() == 150
        assert pixel.green() == 100
        assert pixel.blue() == 50


class TestScaleToFit:
    def test_downscale_preserves_aspect(self):
        img = QImage(1920, 1080, QImage.Format.Format_RGB888)
        scaled = scale_to_fit(img, 720, 500)
        assert scaled.width() <= 720
        assert scaled.height() <= 500
        # Aspect ratio: 1920/1080 = 16/9
        ratio = scaled.width() / scaled.height()
        assert abs(ratio - 16 / 9) < 0.02

    def test_no_upscale_when_smaller(self):
        img = QImage(320, 240, QImage.Format.Format_RGB888)
        scaled = scale_to_fit(img, 720, 500)
        assert scaled.width() == 320
        assert scaled.height() == 240

    def test_exact_fit(self):
        img = QImage(720, 500, QImage.Format.Format_RGB888)
        scaled = scale_to_fit(img, 720, 500)
        assert scaled.width() == 720
        assert scaled.height() == 500
