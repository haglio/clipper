"""Content overlay — the private values this checkout needs at runtime.

The suite root (where the media library and the sibling apps live) and the
status file the main player publishes into are machine-specific, so they come
from ``content.local.json`` (git-ignored) rather than from source.  A committed
``content.example.json`` documents the shape and is what a fresh or public
checkout loads.

**The read is cached; the parse is not.** Every consumer asks at the moment it
needs the value rather than at import, so the same file would otherwise be read
and parsed once per question — including on every keystroke in the launcher's
video field.  What is cached is the file's text, keyed by the path it came
from, so each caller still gets a dictionary of its own and one module's edit
of what it was handed can never be every other module's edit.
``load_content.cache_clear()`` drops it, which a test pointing ``LOCAL_CONTENT``
somewhere new needs.
"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from app_support.overlay import overlay_path

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOCAL_CONTENT = PROJECT_DIR / "content.local.json"
EXAMPLE_CONTENT = PROJECT_DIR / "content.example.json"


@cache
def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_content(
    local_path: Path | None = None,
    example_path: Path | None = None,
) -> dict[str, Any]:
    """The local overlay's content when present, else the committed example."""
    return json.loads(_text(overlay_path(
        LOCAL_CONTENT if local_path is None else local_path,
        EXAMPLE_CONTENT if example_path is None else example_path,
    )))


load_content.cache_clear = _text.cache_clear
