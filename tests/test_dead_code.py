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

# Qt method overrides — called by the Qt event loop, not user code.
_QT_OVERRIDES: set[tuple[str, str]] = {
    ("clipper/gui/legend_widget.py", "paintEvent"),
    ("clipper/gui/main_window.py", "paintEvent"),
    ("clipper/gui/main_window.py", "closeEvent"),
    ("clipper/gui/main_window.py", "keyPressEvent"),
    ("clipper/gui/timeline_widget.py", "mousePressEvent"),
    ("clipper/gui/timeline_widget.py", "paintEvent"),
    ("clipper/gui/video_pane.py", "paintEvent"),
}

# Python runtime hooks.
_PYTHON_HOOKS: set[tuple[str, str]] = {
    ("clipper/__init__.py", "__getattr__"),
}

# Dataclass / namedtuple fields accessed dynamically (obj.attr).
# Vulture can't trace attribute access on dynamically-typed objects.
_DATACLASS_FIELDS: set[tuple[str, str]] = set()

# config.py — ALL fields are loaded from JSON and accessed as config.field.
_CONFIG_FILE = "clipper/config.py"

# state.py — dataclass fields read/written by production code.
_STATE_FILE = "clipper/state.py"

# ExportJob mutations — export pipeline writes these during long-running ops.
_EXPORT_MUTATIONS: set[tuple[str, str]] = {
    ("clipper/export_steps.py", "stage"),
    ("clipper/export_steps.py", "clip_status"),
    ("clipper/export_steps.py", "raw_clip_output"),
    ("clipper/export_steps.py", "fix_status"),
    ("clipper/gui/export_worker.py", "fix_status"),
    ("clipper/export_steps.py", "clip_output"),
    ("clipper/export_steps.py", "audio_status"),
    ("clipper/export_steps.py", "audio_output"),
}

# Attribute mutations on state objects — used by production code but vulture
# can't trace setattr on dynamic types.
_STATE_MUTATIONS: set[tuple[str, str]] = {
    ("clipper/frame_store.py", "render_rev"),
    ("clipper/loop_suggestions.py", "render_rev"),
    ("clipper/playback.py", "render_rev"),
    ("clipper/gui/main_window.py", "render_rev"),
    ("clipper/gui/main_window.py", "_export_worker"),
    ("clipper/gui/export_worker.py", "done"),
    ("clipper/gui/export_worker.py", "active"),
    ("clipper/session_launch.py", "original_session_payload"),
    ("clipper/session_persistence.py", "last_saved_payload"),
    ("clipper/state_factory.py", "last_saved_payload"),
}

WHITELIST: set[tuple[str, str]] = (
    _QT_OVERRIDES
    | _PYTHON_HOOKS
    | _DATACLASS_FIELDS
    | _EXPORT_MUTATIONS
    | _STATE_MUTATIONS
)

# Files where ALL findings are whitelisted (every field is dynamically accessed).
_WHITELISTED_FILES: set[str] = {_CONFIG_FILE, _STATE_FILE}


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
        if rel in _WHITELISTED_FILES:
            continue
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
