from __future__ import annotations

from pathlib import Path

BOUNDS_EXTEND_LEFT_KEYS = {ord("a"), ord("A")}
BOUNDS_CONTRACT_LEFT_KEYS = {ord("s"), ord("S")}
BOUNDS_CONTRACT_RIGHT_KEYS = {ord("d"), ord("D")}
BOUNDS_EXTEND_RIGHT_KEYS = {ord("f"), ord("F")}
WIN_LEFT_KEYS = {2424832, 81}
WIN_RIGHT_KEYS = {2555904, 83}
ESC_KEYS = {27}
QUIT_KEYS = {ord("q"), ord("Q")}
MARK_IN_KEYS = {ord("i"), ord("I"), ord("["), 91}
MARK_OUT_KEYS = {ord("o"), ord("O"), ord("]"), 93}
ACCEPT_SUGGESTED_IN_KEYS = {ord("9")}
ACCEPT_SUGGESTED_OUT_KEYS = {ord("0")}
SHIFT_RANGE_LEFT_KEYS = {ord(","), ord("<")}
SHIFT_RANGE_RIGHT_KEYS = {ord("."), ord(">")}
WRAP_TOGGLE_KEYS = {ord("w"), ord("W")}
LOOP_MODE_CYCLE_KEYS = {ord("l"), ord("L")}
PLAY_PAUSE_KEYS = {32}
SPEED_DOWN_KEYS = {ord("-"), ord("_")}
SPEED_UP_KEYS = {ord("+"), ord("="), ord("=")}
ENTER_KEYS = {13, 10}
TAB_KEYS = {9}

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


__all__ = [
    "AUDIO_DIR",
    "ACCEPT_SUGGESTED_IN_KEYS",
    "ACCEPT_SUGGESTED_OUT_KEYS",
    "BOUNDS_CONTRACT_LEFT_KEYS",
    "BOUNDS_CONTRACT_RIGHT_KEYS",
    "BOUNDS_EXTEND_LEFT_KEYS",
    "BOUNDS_EXTEND_RIGHT_KEYS",
    "CLIPS_DIR",
    "VR_CLIPS_DIR",
    "CLIP_POSTPROCESS_SCRIPT",
    "FRAMES_DIR",
    "ENTER_KEYS",
    "ESC_KEYS",
    "LAST_SESSION_FILE",
    "LOOP_MODE_CYCLE_KEYS",
    "MARK_IN_KEYS",
    "MARK_OUT_KEYS",
    "MODULE_DIR",
    "PLAY_PAUSE_KEYS",
    "QUIT_KEYS",
    "RAW_CLIPS_DIR",
    "SESSIONS_DIR",
    "SHIFT_RANGE_LEFT_KEYS",
    "SHIFT_RANGE_RIGHT_KEYS",
    "SPEED_DOWN_KEYS",
    "SPEED_UP_KEYS",
    "TAB_KEYS",
    "WIN_LEFT_KEYS",
    "WIN_RIGHT_KEYS",
    "WRAP_TOGGLE_KEYS",
    "ensure_runtime_dirs",
]
