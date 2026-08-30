from __future__ import annotations

import json
from pathlib import Path

from clipper.content import EXAMPLE_CONTENT, load_content

# The media library lives outside the checkout and its location is private;
# it reaches the code through the content overlay.
_SUITE_ROOT = Path(load_content()["suite_root"])

# What the committed example documents the shape with, and therefore the one
# value that names no library.
_PLACEHOLDER_SUITE_ROOT = Path(
    json.loads(EXAMPLE_CONTENT.read_text(encoding="utf-8"))["suite_root"]
)

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
SESSIONS_DIR = PROJECT_DIR / "sessions"
RAW_CLIPS_DIR = PROJECT_DIR / "raw_clips"
_GENAU_DIR = _SUITE_ROOT / "videos" / "genau"
CLIPS_DIR = _GENAU_DIR / "clips"
VR_CLIPS_DIR = _GENAU_DIR / "vr_clips"
AUDIO_DIR = _GENAU_DIR / "audio"
LAST_SESSION_FILE = SESSIONS_DIR / ".last_session.txt"
CLIP_POSTPROCESS_SCRIPT = PACKAGE_DIR / "clip_postprocess.py"


def library_is_configured() -> bool:
    """Whether ``suite_root`` names a real library or the example's placeholder.

    The value, not which file it came from.  Setting a machine up means copying
    ``content.example.json`` to ``content.local.json`` and then editing it, and
    between those two steps the overlay is local and ``suite_root`` is still
    ``C:/path/to/suite-root`` — so "is there a local overlay" answers yes at
    exactly the moment there is still no library.
    """
    return _SUITE_ROOT != _PLACEHOLDER_SUITE_ROOT


def ensure_runtime_dirs() -> None:
    """Create what clipper writes into, as far as this machine has somewhere.

    The first two are inside the checkout and always made.  The library folders
    are derived from ``suite_root``, which is a placeholder until a local
    overlay supplies one: on POSIX ``C:/path/to/suite-root`` is a *relative*
    path, so making them put a literal ``C:`` tree inside the repo, and on
    Windows it put ``C:\\path\\to\\suite-root`` on the system drive.  A checkout
    with no overlay has no library to export into, so it gets no folders
    pretending otherwise.
    """
    for directory in (SESSIONS_DIR, RAW_CLIPS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    if not library_is_configured():
        return
    for directory in (CLIPS_DIR, VR_CLIPS_DIR, AUDIO_DIR):
        directory.mkdir(parents=True, exist_ok=True)


# The characters Windows will not take in a filename.  Named rather than inline
# so a test can walk the list instead of carrying its own copy of it.
FORBIDDEN_NAME_CHARS = '<>:"/\\|?*'


def sanitize_name(name: str) -> str:
    """The session name as a filename this app can find again.

    Lives here because every path this module builds out of a session name is
    built from the sanitized form; keeping the two apart is what let
    `create_session` write one file and the rest of the app look for another.
    """
    name = name.strip()
    for ch in FORBIDDEN_NAME_CHARS:
        name = name.replace(ch, "_")
    return name.strip().rstrip(".")
