from __future__ import annotations

from pathlib import Path, PureWindowsPath

from app_support.overlay import overlay_value

from clipper.content import EXAMPLE_CONTENT, LOCAL_CONTENT, PROJECT_DIR, load_content

# The checkout root is `content`'s: it needs one to find the overlay beside it,
# and cannot ask this module for it, since this module asks it for the overlay.
PACKAGE_DIR = Path(__file__).resolve().parent
SESSIONS_DIR = PROJECT_DIR / "sessions"
RAW_CLIPS_DIR = PROJECT_DIR / "raw_clips"
LAST_SESSION_FILE = SESSIONS_DIR / ".last_session.txt"
CLIP_POSTPROCESS_SCRIPT = PACKAGE_DIR / "clip_postprocess.py"


def suite_root() -> Path:
    """Where the media library lives, as this machine's overlay names it.

    Asked at the call rather than read into a constant at import: a module that
    reads the overlay to be imported makes every consumer -- a test, a tool,
    another app's smoke check -- pay for the file and inherit whichever copy
    happened to be on disk first.  ``load_content`` caches the text, so asking
    repeatedly costs one read.
    """
    return Path(overlay_value(load_content(), "suite_root", path=LOCAL_CONTENT))


def _placeholder_suite_root() -> Path:
    """What the committed example documents the shape with, and therefore the
    one ``suite_root`` that names no library.  It is the example that is wanted
    whichever overlay this machine has, so both arguments are the example.
    """
    return Path(load_content(EXAMPLE_CONTENT, EXAMPLE_CONTENT)["suite_root"])


def _genau_dir() -> Path:
    """The output tree genau reads, which is what clipper exports into."""
    return suite_root() / "videos" / "genau"


def clips_dir() -> Path:
    return _genau_dir() / "clips"


def vr_clips_dir() -> Path:
    return _genau_dir() / "vr_clips"


def audio_dir() -> Path:
    return _genau_dir() / "audio"


def vr_video_dir() -> PureWindowsPath:
    """The library folder whose videos are VR, which is what the launcher's
    checkbox reads to decide whether an export lands in ``vr_clips``.

    A pure Windows path: what it is compared against is whatever the file
    dialog handed the launcher on the machine the app runs on, and that machine
    is a Windows one.  A native path would make the comparison a no-op
    everywhere else, which is where the tests run.
    """
    return PureWindowsPath(suite_root()) / "videos" / "videos" / "VR"


def library_is_configured() -> bool:
    """Whether ``suite_root`` names a real library or the example's placeholder.

    The value, not which file it came from.  Setting a machine up means copying
    ``content.example.json`` to ``content.local.json`` and then editing it, and
    between those two steps the overlay is local and ``suite_root`` is still
    ``C:/path/to/suite-root`` — so "is there a local overlay" answers yes at
    exactly the moment there is still no library.
    """
    return suite_root() != _placeholder_suite_root()


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
    for directory in (clips_dir(), vr_clips_dir(), audio_dir()):
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
