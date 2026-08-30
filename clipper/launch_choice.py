"""What the launcher dialog was asked for: one of three shapes.

It used to be one untyped dict keyed on a `"mode"` string, so consumers
branched on the string and then indexed keys that exist in only one of the
three shapes -- `info["session_json"]` is a `KeyError` on two of them, and
nothing said so.  Three types say it instead, and the consumer dispatches on
which one it is.

Qt-free, because `session_launch` reads these and the dialog writes them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .loop_modes import LOOP_MODE_BASE_TIP_BASE


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
    loop_mode: str = LOOP_MODE_BASE_TIP_BASE
    vr: bool = False


@dataclass(frozen=True)
class ClipWholeVideo:
    """Export a whole video with no editor at all."""

    video_file: str


LaunchChoice = LoadSession | NewSession | ClipWholeVideo
