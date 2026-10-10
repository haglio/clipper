"""Convert OpenCV BGR numpy frames to Qt QImage / QPixmap."""

from __future__ import annotations

import cv2
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap


def bgr_to_qimage(frame: np.ndarray) -> QImage:
    """Convert a BGR uint8 numpy array to an RGB QImage.

    The returned QImage owns its pixel data (via ``.copy()``), so the
    source array can be safely deleted or overwritten afterwards.
    """
    h, w, ch = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    bytes_per_line = ch * w
    return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()


def scale_to_fit(image: QImage, max_w: int, max_h: int) -> QImage:
    """Scale *image* to fit within *max_w* x *max_h*, preserving aspect ratio.

    Never upscales — returns the original image if it already fits.
    """
    if image.width() <= max_w and image.height() <= max_h:
        return image
    pixmap = QPixmap.fromImage(image)
    scaled = pixmap.scaled(
        max_w,
        max_h,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return scaled.toImage()
