from __future__ import annotations

from pathlib import Path

from .paths import PROJECT_DIR


def clipper_icon_path() -> Path:
    return PROJECT_DIR / "clipper.ico"
