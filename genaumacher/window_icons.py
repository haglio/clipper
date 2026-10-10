from __future__ import annotations

from pathlib import Path

from .paths import PROJECT_DIR


def genaumacher_icon_path() -> Path:
    return PROJECT_DIR / "genaumacher.ico"
