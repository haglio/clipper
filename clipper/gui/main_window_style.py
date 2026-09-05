"""How the main window dresses its widgets: colors, metrics and focus.

One of the six things `ClipperMainWindow` was doing in one class.  Nothing here
knows what a `VideoState` is.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QPushButton, QWidget
from shared_ui.colors import RED, TEXT_SECONDARY
from shared_ui.fonts import FONT_UI, SIZE_SMALL, make_font
from shared_ui.spacing import BUTTON_PAD_H_TIGHT, BUTTON_PAD_V

LABEL_STYLE = f"color: {TEXT_SECONDARY.name()}; background: transparent;"
WARNING_STYLE = f"color: {RED.name()}; background: transparent;"

# The buttons themselves are the family's, from the sheet the application
# wears.  What is this window's own is how tightly they are packed: every
# control here is a fixed square or a fixed short bar, and at the family's
# ordinary side pad a two-character label has no room left inside one.
CHROME_STYLE = f"""
    QPushButton {{
        padding: {BUTTON_PAD_V}px {BUTTON_PAD_H_TIGHT}px;
    }}
"""

# Compact square buttons; the wider ones the labels they carry need.
SMALL_BUTTON = (32, 28)
PLAY_BUTTON = (40, 28)
EXPORT_BUTTON = (72, 28)
WRAP_BUTTON = (64, 28)


def small_font() -> QFont:
    """The label font.  Built on demand, not at import: Qt asks for a
    QGuiApplication before a QFont, and a module-level one is built by the mere
    act of importing this package.  `shared_ui` caches the result."""
    return make_font(FONT_UI, SIZE_SMALL)


def size_controls(button_bar, timeline_controls) -> None:
    """Give every control the family's button metrics."""
    tc, bb = timeline_controls, button_bar
    for button in (tc.shift_left_btn, tc.shift_right_btn,
                   tc.extend_left_btn, tc.contract_left_btn,
                   tc.contract_right_btn, tc.extend_right_btn,
                   tc.mark_in_btn, tc.mark_out_btn,
                   bb.speed_down_btn, bb.speed_up_btn):
        button.setFixedSize(*SMALL_BUTTON)
    bb.play_pause_btn.setFixedSize(*PLAY_BUTTON)
    bb.export_btn.setFixedSize(*EXPORT_BUTTON)
    tc.wrap_btn.setFixedSize(*WRAP_BUTTON)


def refuse_focus(window: QWidget) -> None:
    """Every key must reach keyPressEvent, so no button takes focus."""
    for button in window.findChildren(QPushButton):
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
