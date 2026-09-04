"""Custom-painted keycap shortcut legend."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QFont, QPainter
from PyQt6.QtWidgets import QWidget
from shared_ui.colors import (
    BG_KEYCAP,
    BG_PRIMARY,
    BORDER_DEFAULT,
    TEXT_LEGEND_JOIN,
    TEXT_LEGEND_LABEL,
    TEXT_PRIMARY,
)
from shared_ui.fonts import FONT_UI, SIZE_SMALL, SIZE_TINY

if TYPE_CHECKING:
    from .shortcuts import LegendEntry

# Keycap metrics.  Every one of these used to appear twice, once in the pass
# that measures a row and once in the pass that draws it, so changing the size
# of a keycap meant changing it in both or the row silently mis-centered.
KEYCAP_PADDING = 12
KEYCAP_MIN_WIDTH = 24
KEYCAP_HEIGHT = 22
KEYCAP_GAP = 2
JOINER_GAP = 4
LABEL_GAP = 16


class LegendWidget(QWidget):
    """Paints whatever rows it is given, keycap style.

    It is handed its rows rather than fetching them.  Reaching for
    `shortcuts.legend_rows()` here would bind the whole action layer at import
    -- `shortcuts` names the editing functions, which reach `frame_store`,
    which imports cv2 -- so a widget whose only job is drawing keycaps would
    need the video decoder to be importable at all.  It did not before this
    table existed and it does not now.
    """

    def __init__(self, rows: tuple[tuple[LegendEntry, ...], ...],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.legend_rows = rows
        self.setMinimumHeight(80)

    # -- Metrics ---------------------------------------------------------------
    # Each answers "how far along does this move x", and the drawing pass
    # advances by exactly what the measuring pass counted.

    def _keycap_width(self, p: QPainter, key: str, font: QFont) -> int:
        p.setFont(font)
        advance = p.fontMetrics().horizontalAdvance(key)
        return max(advance + KEYCAP_PADDING, KEYCAP_MIN_WIDTH)

    def _joiner_width(self, p: QPainter, joiner: str, font: QFont) -> int:
        p.setFont(font)
        return p.fontMetrics().horizontalAdvance(joiner) + JOINER_GAP

    def _label_width(self, p: QPainter, label: str, font: QFont) -> int:
        p.setFont(font)
        return p.fontMetrics().horizontalAdvance(f": {label}") + LABEL_GAP

    def _row_width(self, p: QPainter, row, key_font, label_font, join_font) -> int:
        """Pre-calculate the total pixel width of a legend row."""
        width = 0
        for keys, joiner, label in row:
            for i, key in enumerate(keys):
                if i > 0 and joiner:
                    width += self._joiner_width(p, joiner, join_font)
                width += self._keycap_width(p, key, key_font) + KEYCAP_GAP
            width += self._label_width(p, label, label_font)
        return width

    # -- Painting --------------------------------------------------------------

    def _draw_keycap(self, p: QPainter, x: int, top: int, key: str, font: QFont) -> int:
        """Draw one keycap with its glyph centered; returns how far x moves."""
        width = self._keycap_width(p, key, font)
        cap = QRectF(x, top, width, KEYCAP_HEIGHT)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BG_KEYCAP)
        p.drawRoundedRect(cap, 4, 4)

        p.setPen(BORDER_DEFAULT)
        p.drawRoundedRect(cap, 4, 4)

        metrics = p.fontMetrics()
        p.setPen(TEXT_PRIMARY)
        p.drawText(
            int(x + (width - metrics.horizontalAdvance(key)) / 2),
            int(top + KEYCAP_HEIGHT / 2 + metrics.ascent() / 2 - 1),
            key,
        )
        return width + KEYCAP_GAP

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), BG_PRIMARY)

        key_font = QFont(FONT_UI, SIZE_SMALL)
        key_font.setBold(True)
        label_font = QFont(FONT_UI, SIZE_TINY)
        join_font = QFont(FONT_UI, SIZE_TINY)

        row_height = self.height() // max(1, len(self.legend_rows))

        for row_idx, row in enumerate(self.legend_rows):
            y = row_idx * row_height
            baseline = y + row_height // 2 + 4
            cap_top = y + (row_height - KEYCAP_HEIGHT) // 2
            x = max(8, (self.width() - self._row_width(p, row, key_font, label_font, join_font)) // 2)

            for keys, joiner, label in row:
                for i, key in enumerate(keys):
                    if i > 0 and joiner:
                        p.setFont(join_font)
                        p.setPen(TEXT_LEGEND_JOIN)
                        p.drawText(x + 2, baseline, joiner)
                        x += self._joiner_width(p, joiner, join_font)

                    x += self._draw_keycap(p, x, cap_top, key, key_font)

                p.setFont(label_font)
                p.setPen(TEXT_LEGEND_LABEL)
                p.drawText(x + 4, baseline, f": {label}")
                x += self._label_width(p, label, label_font)

        p.end()
