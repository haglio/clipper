"""Tests for clipper.gui.video_pane — video frame display widget."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest
from shared_ui.colors import BG_SECONDARY

from clipper.gui.frame_converter import bgr_to_qimage
from clipper.gui.video_pane import VideoPane


@pytest.fixture
def pane():
    return VideoPane()


@pytest.fixture
def sample_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (50, 100, 150)  # BGR
    return frame


def _drawn_box(image, background: str):
    """The bounding box of everything painted over the pane's background."""
    inked = [
        (x, y)
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).name() != background
    ]
    if not inked:
        return None
    xs = [x for x, _ in inked]
    ys = [y for _, y in inked]
    return (min(xs), min(ys), max(xs), max(ys))


class TestConstruction:
    def test_minimum_size_set(self, pane):
        assert pane.minimumWidth() >= 320
        assert pane.minimumHeight() >= 240


class TestSetFrame:
    def test_set_frame_triggers_update(self, pane, sample_frame):
        qimg = bgr_to_qimage(sample_frame)
        with patch.object(pane, "update") as mock_update:
            pane.set_frame(qimg)
            mock_update.assert_called_once()


class TestPainting:
    """What the pane shows, not what it stores.

    Every assertion here used to read `pane._image`, and nothing looked at a
    painted pixel -- so replacing ``paintEvent``'s body with ``return`` left the
    whole suite at baseline apart from the dead-code guard.
    """

    @pytest.fixture
    def small_frame(self):
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        frame[:] = (50, 100, 150)  # BGR
        return frame

    def test_an_empty_pane_is_all_background(self, pane, rendered):
        pane.resize(400, 300)

        image = rendered(pane)

        assert _drawn_box(image, BG_SECONDARY.name()) is None

    def test_it_draws_the_frame_centered_at_its_own_size(self, pane, rendered, small_frame):
        pane.resize(400, 300)

        pane.set_frame(bgr_to_qimage(small_frame))
        image = rendered(pane)

        assert image.pixelColor(200, 150).name() == "#966432"  # the frame, as RGB
        assert _drawn_box(image, BG_SECONDARY.name()) == (100, 100, 299, 199)

    def test_a_new_frame_replaces_the_one_before_it(self, pane, rendered, small_frame):
        pane.resize(400, 300)
        pane.set_frame(bgr_to_qimage(small_frame))

        wider = np.zeros((100, 300, 3), dtype=np.uint8)
        wider[:] = (10, 20, 30)
        pane.set_frame(bgr_to_qimage(wider))
        image = rendered(pane)

        assert image.pixelColor(200, 150).name() == "#1e140a"
        assert _drawn_box(image, BG_SECONDARY.name()) == (50, 100, 349, 199)

    def test_clearing_the_frame_wipes_what_was_drawn(self, pane, rendered, small_frame):
        pane.resize(400, 300)
        pane.set_frame(bgr_to_qimage(small_frame))

        pane.set_frame(None)
        image = rendered(pane)

        assert _drawn_box(image, BG_SECONDARY.name()) is None
