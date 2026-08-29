"""Dead-code guardrail — fail if vulture finds unlisted dead code."""
from __future__ import annotations

from pathlib import Path

import vulture

_PROJECT = Path(__file__).resolve().parents[1]
_CLIPPER = _PROJECT / "clipper"

# ---- Whitelist: false positives proven to be framework/platform callbacks ----
#
# Format: {(relative_posix_path, name)} — keeps the set readable and diffable.
# Only add entries that are *provably* invoked by a framework, platform API,
# or dynamic attribute access (dataclass fields accessed via obj.attr).
#
# Entries are (path, name) pairs and nothing else.  This used to carry a second
# set that exempted clipper/config.py and clipper/state.py whole, on the stated
# grounds that every field in them was read dynamically.  Neither was true, and
# a file-wide exemption cannot fail: the two files holding the most dead surface
# in the repo were the two the gate could never see, and it hid 67 findings.

# Qt method overrides — called by the Qt event loop, not user code.
_QT_OVERRIDES: set[tuple[str, str]] = {
    ("clipper/gui/legend_widget.py", "paintEvent"),
    ("clipper/gui/main_window.py", "paintEvent"),
    ("clipper/gui/main_window.py", "closeEvent"),
    ("clipper/gui/timeline_widget.py", "mousePressEvent"),
    ("clipper/gui/timeline_widget.py", "paintEvent"),
    ("clipper/gui/video_pane.py", "paintEvent"),
}

# ExportJob mutations — the export steps write these and the Qt signal bridge
# forwards them to the dialog from __setattr__, which vulture cannot follow.
_EXPORT_MUTATIONS: set[tuple[str, str]] = {
    ("clipper/export_steps.py", "stage"),
}

# Attribute mutations on state objects — used by production code but vulture
# can't trace setattr on dynamic types.
_STATE_MUTATIONS: set[tuple[str, str]] = {
    ("clipper/frame_store.py", "render_rev"),
    ("clipper/loop_suggestions.py", "render_rev"),
    ("clipper/playback.py", "render_rev"),
    ("clipper/gui/main_window.py", "render_rev"),
    ("clipper/gui/main_window.py", "_export_worker"),
    ("clipper/session_launch.py", "original_session_payload"),
    ("clipper/session_persistence.py", "last_saved_payload"),
    ("clipper/state_factory.py", "last_saved_payload"),
}

# The declarations those mutations write to, one line per field, each with the
# reader vulture cannot see.  These are what the file-wide state.py exemption
# used to cover; naming them costs four lines and leaves the rest of the file
# under the gate.
_STATE_FIELDS: set[tuple[str, str]] = {
    # ExportJob.stage — read by _SignalBridge.__setattr__ (gui/export_worker.py:57),
    # which turns the write into the dialog's stage_changed signal.
    ("clipper/state.py", "stage"),
    # VideoState.original_session_payload — the payload the session was opened
    # with, kept so a discard-on-exit has something to compare against.
    ("clipper/state.py", "original_session_payload"),
    # VideoState.last_saved_payload — the last payload that reached disk.  A
    # failed write leaves it alone, which is how the warning path proves the
    # good copy survived (tests/test_clipper_session_persistence.py:96-100).
    ("clipper/state.py", "last_saved_payload"),
    # VideoState.render_rev — bumped by every edit that changes what is drawn.
    # No production reader consults it: the 60 Hz tick repaints unconditionally,
    # so it survives as the observable the edit tables read to prove an edit
    # happened.  See the 2026-08-29 changelog note.
    ("clipper/state.py", "render_rev"),
}

WHITELIST: set[tuple[str, str]] = (
    _QT_OVERRIDES
    | _EXPORT_MUTATIONS
    | _STATE_MUTATIONS
    | _STATE_FIELDS
)


def _relative_posix(path: str) -> str:
    """Convert an absolute path to a project-relative posix path."""
    try:
        return Path(path).resolve().relative_to(_PROJECT.resolve()).as_posix()
    except ValueError:
        return path


def test_no_dead_code():
    v = vulture.Vulture()
    v.scavenge([_CLIPPER])

    unlisted = []
    for item in v.get_unused_code():
        rel = _relative_posix(item.filename)
        if (rel, item.name) in WHITELIST:
            continue
        unlisted.append(
            f"  {rel}:{item.first_lineno} — unused {item.typ} '{item.name}' "
            f"({item.confidence}% confidence)"
        )

    if unlisted:
        msg = (
            f"Vulture found {len(unlisted)} dead-code item(s) not in the whitelist.\n"
            "Delete genuinely dead code or add proven false positives to the "
            "whitelist in test_dead_code.py:\n" + "\n".join(sorted(unlisted))
        )
        raise AssertionError(msg)
