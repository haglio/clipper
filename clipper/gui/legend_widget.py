"""Custom-painted keycap shortcut legend."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QWidget

from shared_ui.colors import (
    BG_KEYCAP,
    BG_PRIMARY,
    BORDER_DEFAULT,
    TEXT_LEGEND_JOIN,
    TEXT_LEGEND_LABEL,
    TEXT_PRIMARY,
)
from shared_ui.fonts import FONT_MONO, SIZE_SMALL, SIZE_TINY

from clipper.render_canvas import HOTKEY_LEGEND_ROWS

LegendEntry = tuple[tuple[str, ...], str, str]


class LegendWidget(QWidget):
    """Displays keyboard shortcut legend as keycap-style rows."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.legend_rows: tuple[tuple[LegendEntry, ...], ...] = HOTKEY_LEGEND_ROWS
        self.setMinimumHeight(80)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), BG_PRIMARY)

        key_font = QFont(FONT_MONO, SIZE_SMALL)
        key_font.setBold(True)
        label_font = QFont(FONT_MONO, SIZE_TINY)
        join_font = QFont(FONT_MONO, SIZE_TINY)

        row_height = self.height() // max(1, len(self.legend_rows))

        for row_idx, row in enumerate(self.legend_rows):
            y = row_idx * row_height
            x = 8

            for keys, joiner, label in row:
                for i, key in enumerate(keys):
                    if i > 0 and joiner:
                        p.setFont(join_font)
                        p.setPen(TEXT_LEGEND_JOIN)
                        p.drawText(x + 2, y + row_height // 2 + 4, joiner)
                        x += p.fontMetrics().horizontalAdvance(joiner) + 4

                    # Draw keycap
                    p.setFont(key_font)
                    fm = p.fontMetrics()
                    tw = fm.horizontalAdvance(key)
                    kw = max(tw + 12, 24)
                    kh = 22
                    ky = y + (row_height - kh) // 2

                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(BG_KEYCAP)
                    p.drawRoundedRect(QRectF(x, ky, kw, kh), 4, 4)

                    p.setPen(BORDER_DEFAULT)
                    p.drawRoundedRect(QRectF(x, ky, kw, kh), 4, 4)

                    p.setPen(TEXT_PRIMARY)
                    p.drawText(
                        int(x + (kw - tw) / 2),
                        int(ky + kh / 2 + fm.ascent() / 2 - 1),
                        key,
                    )
                    x += kw + 2

                # Draw label
                p.setFont(label_font)
                p.setPen(TEXT_LEGEND_LABEL)
                p.drawText(x + 4, y + row_height // 2 + 4, f": {label}")
                x += p.fontMetrics().horizontalAdvance(f": {label}") + 16

        p.end()
