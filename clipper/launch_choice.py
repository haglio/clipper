"""What the launcher dialog was asked for: one of three shapes.

Three types rather than one dict keyed on a `"mode"` string: a key like
`session_json` exists in only one of the three shapes, so a consumer indexing
it on a dict gets a `KeyError` with nothing having said which shapes carry it.
Here the consumer dispatches on which type it was handed.

Qt-free, because `session_launch` reads these and the dialog writes them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .loop_modes import LoopMode


@dataclass(frozen=True)
class LoadSession:
    """Open a session file that already exists."""

    session_json: str


@dataclass(frozen=True)
class NewSession:
    """Cut a new session out of a video, starting at a timestamp."""

    video_file: str
    session_name: str
    timestamp: str
    seconds: float
    loop_mode: LoopMode = LoopMode.BASE_TIP_BASE
    vr: bool = False


@dataclass(frozen=True)
class ClipWholeVideo:
    """Export a whole video with no editor at all."""

    video_file: str


LaunchChoice = LoadSession | NewSession | ClipWholeVideo
