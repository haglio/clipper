"""What one run of the loop post-process was asked for.

The pipeline read these off an argparse ``Namespace`` typed ``Any``, so the
library layer knew the shape of the command line and nothing but the command
line could call it without faking one.  A record instead: the parser fills it
in, the pipeline reads it, and the defaults live here rather than once in the
parser and again in a ``getattr`` fallback two modules away.

No import of the pipeline or the parser, so both can import this.
"""
from __future__ import annotations

from dataclasses import dataclass

from .loop_modes import LOOP_MODE_BASE_TIP_BASE


@dataclass(frozen=True)
class PostprocessOptions:
    """The settings one post-process run works from, and their defaults."""

    input: str
    output: str
    loop_mode: str = LOOP_MODE_BASE_TIP_BASE
    bridge_ms: float = 80.0
    bridge_frames: int | None = None
    mode: str = "register"
    keep_length: bool = True
    symmetric_blend: int = 0
    seam_ms: float = 250.0
    copy_audio: bool = False
    crf: int = 12
    preset: str = "slow"
    pix_fmt: str = "yuv420p"
    max_mb: float = 1.0
