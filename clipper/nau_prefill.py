"""What Nau is playing, so the launcher can open a session on it.

Fun Time's ``;`` already does this from the other side: it reads Nau's status
file and runs ``clipper.create_session --video <path> --time <seconds>``, so
clipper is told and has to know nothing.  This is the pull side, for opening
clipper on its own rather than from a session — and it reads the same file and
the same two fields, so the two routes cannot disagree about what was playing.

That is the whole of clipper's interface to the rest of the suite.  It replaces
a probe that polled VLC's HTTP port and scraped VLC window titles, and then
hunted the filename it recovered across four folder lists out of fun_time's
config.  Nau publishes an absolute path and an exact playhead, so none of that
searching has anything left to do; and clipper no longer reads fun_time's
config, which is how every other app in the family already works.

Where the file is, is machine-specific, so it comes from clipper's own content
overlay under the name fun_time gives it: ``nau_status_file``.  An overlay that
says nothing means no prefill and a blank launcher, which is also what a
machine with Nau switched off gets.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from .content import load_content
from .paths import sanitize_name
from .timecode import format_seconds

@dataclass(frozen=True)
class SessionPrefill:
    """The three fields the launcher's form has, and nothing beside them."""

    video_file: str
    session_name: str
    timestamp: str


def nau_status_file() -> Path | None:
    """The status file named in the content overlay, if this machine names one."""
    raw = load_content().get("nau_status_file")
    return Path(raw) if raw else None


def _published_values(status_file: Path) -> dict[str, str]:
    """The ``key=value`` lines Nau last wrote, or nothing readable.

    The file is replaced whole rather than truncated in place, so a torn read
    is not expected — but it is one poll of a file another process owns, and
    every way that can go wrong means the same thing here: no prefill.
    """
    try:
        text = status_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    return dict(
        line.split("=", 1) for line in text.splitlines() if "=" in line
    )


def detect_nau_session_prefill(status_file: Path | None = None) -> SessionPrefill | None:
    """What Nau is showing, or None when there is nothing to open a session on."""
    status_file = nau_status_file() if status_file is None else status_file
    if status_file is None:
        return None

    values = _published_values(status_file)
    video = values.get("video", "").strip()
    if not video:
        return None

    try:
        position_seconds = int(values.get("position_ms", "0").strip() or 0) / 1000
    except ValueError:
        # A playhead that will not parse costs the timestamp, not the video:
        # the session simply starts at the beginning.
        position_seconds = 0.0

    # The path is Nau's, so it is written the way Windows writes one whatever
    # is reading it here.
    name = PureWindowsPath(video).stem
    return SessionPrefill(
        video_file=video,
        session_name=sanitize_name(name),
        timestamp=format_seconds(position_seconds),
    )
