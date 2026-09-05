"""Every keyboard shortcut, declared once.

This set used to be written out four times in three modules -- a 22-branch
if/elif chain in `keyPressEvent`, a block of button lambdas in the same
constructor, the legend's own literal table, and 21 cv2-era keycode constants
in `paths.py` (deleted by item 28).  The copies had drifted: the legend never
mentioned `q`, and it showed `-`/`+` while the handler also took `_`/`=`.

Here the keys, the action and the legend wording are one row.  The legend is
generated from it, so it cannot advertise a key nothing is bound to or omit one
that is; the buttons connect to the same callables, so a button and its key
cannot come to mean different things.

Lives under `gui/` because the rows name Qt key codes and act on the window.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt

from clipper.editing import (
    accept_suggested_in,
    accept_suggested_out,
    cycle_loop_mode,
    set_mark_in,
    set_mark_out,
    shift_active_range,
)
from clipper.loaded_bounds import contract_left, contract_right, extend_left, extend_right
from clipper.navigation import move_current_left, move_current_right, toggle_wrap_mode
from clipper.playback import change_speed, toggle_loop_pause

if TYPE_CHECKING:
    from .main_window import ClipperMainWindow

Action = Callable[["ClipperMainWindow"], None]

# A legend entry: the shortcuts it covers, how their keycaps are joined, and
# what it says they do.  One entry can cover two shortcuts -- "adjust left
# bound" is what `a` and `s` do between them.
LegendEntry = tuple[tuple[str, ...], str, str]


def _edits(fn: Callable[..., None], *args: object) -> Action:
    """Wrap an editing function as an action on the window that holds a state."""
    def act(window: ClipperMainWindow) -> None:
        fn(window.state, *args)

    return act


@dataclass(frozen=True)
class Shortcut:
    """One action, everything that reaches it, and what the legend prints.

    `keys` are `event.text()` values; `qt_keys` are the codes for keys that
    carry no text.  `keycaps` is the subset the legend prints: the shift
    variants (`_` for `-`, `9` for `(`, `,` for `<`) are the same physical key
    and printing both would say there are two ways to do it.
    """

    name: str
    action: Action
    keycaps: tuple[str, ...]
    keys: tuple[str, ...] = ()
    qt_keys: tuple[Qt.Key, ...] = ()


SHORTCUTS: tuple[Shortcut, ...] = (
    Shortcut("speed_down", _edits(change_speed, -0.25), ("-",), keys=("-", "_")),
    Shortcut("speed_up", _edits(change_speed, 0.25), ("+",), keys=("+", "=")),
    Shortcut("play_pause", _edits(toggle_loop_pause), ("space",),
             qt_keys=(Qt.Key.Key_Space,)),
    Shortcut("export", lambda window: window.start_export(), ("enter",),
             qt_keys=(Qt.Key.Key_Return, Qt.Key.Key_Enter)),
    Shortcut("extend_left", _edits(extend_left), ("a",), keys=("a",)),
    Shortcut("contract_left", _edits(contract_left), ("s",), keys=("s",)),
    Shortcut("shift_left", _edits(shift_active_range, -1), ("<",), keys=(",", "<")),
    Shortcut("shift_right", _edits(shift_active_range, 1), (">",), keys=(".", ">")),
    Shortcut("cursor_left", _edits(move_current_left), ("left",),
             qt_keys=(Qt.Key.Key_Left,)),
    Shortcut("cursor_right", _edits(move_current_right), ("right",),
             qt_keys=(Qt.Key.Key_Right,)),
    Shortcut("mark_in", _edits(set_mark_in), ("i", "["), keys=("i", "[")),
    Shortcut("mark_out", _edits(set_mark_out), ("o", "]"), keys=("o", "]")),
    Shortcut("contract_right", _edits(contract_right), ("d",), keys=("d",)),
    Shortcut("extend_right", _edits(extend_right), ("f",), keys=("f",)),
    Shortcut("accept_in", _edits(accept_suggested_in), ("(",), keys=("9", "(")),
    Shortcut("accept_out", _edits(accept_suggested_out), (")",), keys=("0", ")")),
    Shortcut("toggle_wrap", _edits(toggle_wrap_mode), ("w",), keys=("w",)),
    Shortcut("cycle_loop_mode", _edits(cycle_loop_mode), ("l",), keys=("l",)),
    Shortcut("quit", lambda window: window.close(), ("q",), keys=("q",)),
)

# What the legend says, row by row.  The keycaps are not written here -- they
# come from the shortcuts named, which is what stops the two disagreeing.
# Which entry sits in which row is a free choice, and it is made so the rows
# come out even: the widest has to fit the window's 900 px minimum, and a
# six-entry bounds row did not (bug 56).  Transport and loop; the bounds
# with the cursor between them and the wrap; the in-out edits together.
LEGEND_ROWS: tuple[tuple[LegendEntry, ...], ...] = (
    (
        (("speed_down", "speed_up"), " or ", "speed"),
        (("play_pause",), "", "play or pause preview"),
        (("export",), "", "export"),
        (("quit",), "", "quit"),
        (("cycle_loop_mode",), "", "cycle loop type"),
    ),
    (
        (("extend_left", "contract_left"), " or ", "adjust left bound"),
        (("cursor_left", "cursor_right"), " or ", "move cursor"),
        (("contract_right", "extend_right"), " or ", "adjust right bound"),
        (("toggle_wrap",), "", "toggle cursor wrap mode"),
    ),
    (
        (("shift_left", "shift_right"), " or ", "shift in-out"),
        (("mark_in",), "/", "mark in"),
        (("mark_out",), "/", "mark out"),
        (("accept_in", "accept_out"), " or ", "accept in or out suggestion"),
    ),
)

BY_NAME: dict[str, Shortcut] = {s.name: s for s in SHORTCUTS}
_BY_TEXT: dict[str, Shortcut] = {key: s for s in SHORTCUTS for key in s.keys}
_BY_CODE: dict[int, Shortcut] = {code: s for s in SHORTCUTS for code in s.qt_keys}


def shortcut_for(key: int, text: str) -> Shortcut | None:
    """The shortcut a key press reaches, by code first and then by text."""
    return _BY_CODE.get(key) or _BY_TEXT.get(text)


def legend_rows() -> tuple[tuple[LegendEntry, ...], ...]:
    """The legend in the shape the widget paints, keycaps drawn from the table."""
    return tuple(
        tuple(
            (
                tuple(cap for name in names for cap in BY_NAME[name].keycaps),
                joiner,
                label,
            )
            for names, joiner, label in row
        )
        for row in LEGEND_ROWS
    )
