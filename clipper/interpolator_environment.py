"""What is wrong with this checkout's frame interpolator, if anything.

``clip_postprocess_pipeline`` reaches for RIFE on every clip the loop fix
touches and, finding none, falls back to its geometric seam without a word -- so
a checkout that never ran ``tools/fetch_rife.py`` writes visibly worse clips and
looks fine doing it.  The files are 17 MB this repo deliberately does not track,
which makes "never fetched" the ordinary state of a fresh clone.

This ran as four pytest tests gated on the interpolator, which meant the merge
gate -- which fetches it on purpose -- enforced nothing about a machine that had
not, and the suite stayed four skips short of green.  It belongs where failing
is useful: on the way up, on the machine that makes the clips.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from clipper.content import PROJECT_DIR

VENDORED_EXE = Path("tools") / "rife-ncnn-vulkan-20221029-windows" / "rife-ncnn-vulkan.exe"
MODEL_DIR_NAME = "rife-v4.6"
MODEL_FILES = ("flownet.bin", "flownet.param")

_FETCH = "run `python tools/fetch_rife.py` -- see CLAUDE.md, Fetching RIFE"
_FALLBACK = "the loop fix falls back to its geometric seam"


def _find_exe() -> Path | None:
    """The interpolator this checkout will use, or None if it has none.

    The fetched copy first and whatever is on PATH second, so a machine with a
    system-wide build still interpolates and a checkout that fetched its own is
    not overridden by one.
    """
    on_path = shutil.which(VENDORED_EXE.stem)
    candidates = (PROJECT_DIR / VENDORED_EXE, Path(on_path) if on_path else None)
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    return None


def _missing_weights(exe: Path) -> list[str]:
    """The model files the interpolator needs and this checkout has not got.

    Empty counts as absent: an interrupted extract, or a restored cache, leaves
    a file that exists and holds nothing.
    """
    model_dir = exe.parent / MODEL_DIR_NAME
    return [name for name in MODEL_FILES
            if not (model_dir / name).is_file() or (model_dir / name).stat().st_size == 0]


def locate() -> tuple[Path, Path] | None:
    """The interpolator and the models beside it, or None when the loop fix has
    to do without.  Asked before a clip is fixed, and asked again by
    :func:`complaints` on the way up so the answer is not a surprise."""
    exe = _find_exe()
    if exe is None or _missing_weights(exe):
        return None
    return exe, exe.parent / MODEL_DIR_NAME


def complaints() -> list[str]:
    """What this machine's interpolator setup costs the loop fix, if anything."""
    exe = _find_exe()
    if exe is None:
        return [f"there is none in this checkout, so {_FALLBACK}; {_FETCH}"]
    missing = _missing_weights(exe)
    if missing:
        return [f"{exe} has no {' or '.join(missing)} beside it, so {_FALLBACK}; {_FETCH}"]
    return []
