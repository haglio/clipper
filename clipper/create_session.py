"""Create a Clipper session JSON from a video path and timestamp.

This module is the single source of truth for headless session creation.
Clipper's own launcher uses it for new sessions, and external tools
(e.g. fun_time) invoke it via the CLI entry point.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from app_support.subprocess_utils import hidden_subprocess_kwargs

from .paths import LAST_SESSION_FILE, SESSIONS_DIR
from .utils import sanitize_name

logger = logging.getLogger(__name__)

DEFAULT_SECONDS = 5.0
DEFAULT_LOOP_MODE = "base-tip-base"


def _ffprobe_video_metadata(video_path: str) -> tuple[float, int]:
    """Return (fps, total_frames) via ffprobe.  Raises on failure."""
    kwargs = hidden_subprocess_kwargs()

    def _probe(show_entries: str) -> str:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", show_entries,
                "-of", "csv=p=0",
                video_path,
            ],
            capture_output=True,
            text=True,
            **kwargs,
        )
        return result.stdout.strip()

    fps_raw = _probe("stream=r_frame_rate")
    if not fps_raw:
        raise RuntimeError(f"ffprobe returned no fps for {video_path}")
    if "/" in fps_raw:
        num, den = fps_raw.split("/", 1)
        fps = float(num) / float(den)
    else:
        fps = float(fps_raw)
    if fps <= 0:
        raise RuntimeError(f"Invalid fps ({fps}) for {video_path}")

    frames_raw = _probe("stream=nb_frames")
    if not frames_raw or not frames_raw.isdigit():
        duration_raw = _probe("format=duration")
        if not duration_raw:
            raise RuntimeError(f"ffprobe returned no frame count or duration for {video_path}")
        total_frames = max(1, int(round(float(duration_raw) * fps)))
    else:
        total_frames = int(frames_raw)
    if total_frames <= 0:
        raise RuntimeError(f"Invalid frame count ({total_frames}) for {video_path}")

    return fps, total_frames


def build_session_payload(
    video_path: str,
    start_time_s: float,
    fps: float,
    total_frames: int,
    *,
    session_name: str = "",
    seconds: float = DEFAULT_SECONDS,
    loop_mode: str = DEFAULT_LOOP_MODE,
    vr: bool = False,
) -> dict:
    """Build the session payload dict without touching the filesystem."""
    if not session_name:
        session_name = sanitize_name(Path(video_path).stem)

    base_step = max(1, int(round(fps)))
    start_idx = max(0, min(total_frames - 1, int(round(start_time_s * fps))))
    duration_frames = max(1, int(round(seconds * fps)))
    end_idx = min(total_frames - 1, start_idx + duration_frames - 1)

    return {
        "version": 1,
        "session_name": session_name,
        "video_path": video_path,
        "fps": fps,
        "total_frames": total_frames,
        "loaded_start": start_idx,
        "loaded_end": end_idx,
        "active_start": start_idx,
        "active_end": end_idx,
        "current": start_idx,
        "seconds_per_step": base_step / fps,
        "loop_mode": loop_mode,
        "wrap_mode": "blue",
        "speed": 1.0,
        "vr": vr,
    }


def create_session(
    video_path: str,
    start_time_s: float,
    *,
    session_name: str = "",
    seconds: float = DEFAULT_SECONDS,
    loop_mode: str = DEFAULT_LOOP_MODE,
    vr: bool = False,
    sessions_dir: Path | None = None,
) -> Path:
    """Create a Clipper session JSON and return the file path.

    If a session file with the same name already exists, returns its path
    without overwriting.
    """
    if sessions_dir is None:
        sessions_dir = SESSIONS_DIR
    sessions_dir.mkdir(parents=True, exist_ok=True)

    fps, total_frames = _ffprobe_video_metadata(video_path)

    if not session_name:
        session_name = sanitize_name(Path(video_path).stem)

    session_path = sessions_dir / f"{session_name}.json"
    if session_path.exists():
        logger.info("Session already exists: %s", session_path)
        _update_last_session(session_path)
        return session_path

    payload = build_session_payload(
        video_path,
        start_time_s,
        fps,
        total_frames,
        session_name=session_name,
        seconds=seconds,
        loop_mode=loop_mode,
        vr=vr,
    )

    tmp = session_path.with_suffix(session_path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        os.replace(tmp, session_path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        raise

    logger.info("Created session: %s", session_path)
    _update_last_session(session_path)
    return session_path


def _update_last_session(session_path: Path) -> None:
    try:
        LAST_SESSION_FILE.write_text(str(session_path), encoding="utf-8")
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a Clipper session from a video and timestamp.")
    parser.add_argument("--video", required=True, help="Path to the video file")
    parser.add_argument("--time", required=True, type=float, help="Playback position in seconds")
    parser.add_argument("--name", default="", help="Session name (defaults to video filename stem)")
    parser.add_argument("--seconds", default=DEFAULT_SECONDS, type=float, help="Duration window in seconds")
    args = parser.parse_args(argv)

    try:
        session_path = create_session(
            args.video,
            args.time,
            session_name=args.name,
            seconds=args.seconds,
        )
        print(str(session_path))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
