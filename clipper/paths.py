from __future__ import annotations

from pathlib import Path

from clipper.content import load_content

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
FRAMES_DIR = _GENAU_DIR / "frames"
LAST_SESSION_FILE = SESSIONS_DIR / ".last_session.txt"
CLIP_POSTPROCESS_SCRIPT = MODULE_DIR / "clip_postprocess.py"


def ensure_runtime_dirs() -> None:
    for directory in (SESSIONS_DIR, RAW_CLIPS_DIR, CLIPS_DIR, VR_CLIPS_DIR, AUDIO_DIR, FRAMES_DIR):
        directory.mkdir(parents=True, exist_ok=True)
