from __future__ import annotations

from pathlib import Path

from clipper.content import LOCAL_CONTENT, load_content

# The media library lives outside the checkout and its location is private;
# it reaches the code through the content overlay.
_SUITE_ROOT = Path(load_content()["suite_root"])

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = MODULE_DIR.parent
SESSIONS_DIR = PROJECT_DIR / "sessions"
RAW_CLIPS_DIR = PROJECT_DIR / "raw_clips"
_GENAU_DIR = _SUITE_ROOT / "videos" / "genau"
CLIPS_DIR = _GENAU_DIR / "clips"
VR_CLIPS_DIR = _GENAU_DIR / "vr_clips"
AUDIO_DIR = _GENAU_DIR / "audio"
LAST_SESSION_FILE = SESSIONS_DIR / ".last_session.txt"
CLIP_POSTPROCESS_SCRIPT = MODULE_DIR / "clip_postprocess.py"


def library_is_configured() -> bool:
    """Whether ``suite_root`` names a real library, or the example's placeholder.

    Only ``content.local.json`` carries a real one; the committed example ships
    ``C:/path/to/suite-root`` to document the shape.
    """
    return LOCAL_CONTENT.exists()


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
