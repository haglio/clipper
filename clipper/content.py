"""Content overlay — the private values this checkout needs at runtime.

The suite root (where the media library and the sibling apps live) and the
browser profile are machine-specific, so they come from ``content.local.json``
(git-ignored) rather than from source.  A committed ``content.example.json``
documents the shape and is what a fresh or public checkout loads.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app_support.overlay import read_overlay

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOCAL_CONTENT = PROJECT_DIR / "content.local.json"
EXAMPLE_CONTENT = PROJECT_DIR / "content.example.json"


def load_content(
    local_path: Path | None = None,
    example_path: Path | None = None,
) -> dict[str, Any]:
    """The local overlay's content when present, else the committed example."""
    return read_overlay(LOCAL_CONTENT if local_path is None else local_path,
                        EXAMPLE_CONTENT if example_path is None else example_path)
