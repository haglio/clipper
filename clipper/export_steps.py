from __future__ import annotations

import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import cv2
from app_support.subprocess_utils import hidden_subprocess_kwargs

from .export_progress import ExportProgress
from .paths import CLIP_POSTPROCESS_SCRIPT
from .state import VideoState


def find_tool(name: str) -> str | None:
    """Where `name` is on PATH, if it is anywhere.  Only this module asks."""
    return shutil.which(name)


def _parse_ffmpeg_clock(s: str) -> float:
    try:
        hh, mm, ss = s.split(":")
        return int(hh) * 3600 + int(mm) * 60 + float(ss)
    except Exception:
        return 0.0


def _run_ffmpeg_with_progress(
    cmd: Sequence[str],
    total_duration: float,
    set_progress: Callable[[float], None],
) -> tuple[bool, str]:
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            **hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return False, str(exc)
    progress = 0.0
    error_lines: list[str] = []
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            if "=" not in line:
                error_lines.append(line)
                continue
            key, value = line.split("=", 1)
            partial = None
            if key == "out_time":
                partial = _parse_ffmpeg_clock(value) / max(1e-9, total_duration)
            elif key == "progress" and value == "end":
                partial = 1.0
            if partial is not None:
                progress = max(progress, min(1.0, partial))
                set_progress(progress)
        rc = proc.wait()
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
    if rc != 0:
        detail = "\n".join(error_lines[-20:]).strip()
        prefix = f"ffmpeg exited with code {rc}"
        return False, f"{prefix}\n{detail}" if detail else prefix
    set_progress(1.0)
    return True, ""


def validate_video_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "Output file was not created"
    if path.stat().st_size < 2048:
        return False, "Output file is suspiciously tiny. Another program may have the source video locked. Close that program and retry."
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return False, "Output video is unreadable. Another program may have the source video locked. Close that program and retry."
        ok, _ = cap.read()
        if not ok:
            return False, "Output video contains no readable frames. Another program may have the source video locked. Close that program and retry."
    finally:
        cap.release()
    return True, ""


def export_raw_clip(state: VideoState, out_path: Path, progress: ExportProgress) -> tuple[bool, str]:
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        return False, "ffmpeg not found on PATH"
    clip_duration = max(1.0 / state.fps, (state.active_end - state.active_start + 1) / state.fps)
    start_sec = state.active_start / state.fps
    end_sec = (state.active_end + 1) / state.fps
    # Seek near the target so ffmpeg jumps to a nearby keyframe. Then trim using
    # timestamps relative to the seeked input segment.
    seek_sec = max(0.0, start_sec - 5.0)
    trim_start_rel = max(0.0, start_sec - seek_sec)
    trim_end_rel = trim_start_rel + max(1.0 / state.fps, end_sec - start_sec)
    vf = f"trim=start={trim_start_rel:.6f}:end={trim_end_rel:.6f},setpts=PTS-STARTPTS"
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats", "-stats_period", "0.1",
        "-ss", f"{seek_sec:.6f}", "-i", state.path, "-map", "0:v:0", "-vf", vf, "-r", f"{state.fps:.12g}", "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path),
    ]
    progress.stage("exporting raw silent clip")
    ok, detail = _run_ffmpeg_with_progress(cmd, clip_duration, progress.clip)
    if not ok:
        return False, detail
    ok2, detail2 = validate_video_file(out_path)
    if not ok2:
        return False, detail2
    return True, str(out_path)


def run_clip_postprocess(state: VideoState, raw_path: Path, out_path: Path, progress: ExportProgress) -> tuple[bool, str]:
    progress.stage(f"running {CLIP_POSTPROCESS_SCRIPT.name}")
    if not CLIP_POSTPROCESS_SCRIPT.exists():
        return False, f"{CLIP_POSTPROCESS_SCRIPT.name} not found at {CLIP_POSTPROCESS_SCRIPT}"
    cmd = [sys.executable, str(CLIP_POSTPROCESS_SCRIPT), str(raw_path), "-o", str(out_path), "--loop-mode", state.loop_mode]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **hidden_subprocess_kwargs())
    except Exception as exc:
        return False, str(exc)
    lines = []
    # The script says nothing until it is finished, so this bar is invented:
    # a hundredth per tick, stopping short of full so it cannot claim to be
    # done.  It is unrelated to the work (`all/design/029`); reporting it
    # truthfully means the pipeline emitting progress of its own.
    fraction = 0.0
    while True:
        line = proc.stdout.readline() if proc.stdout else ""
        if line:
            lines.append(line.rstrip())
        if proc.poll() is not None:
            break
        fraction = min(0.95, fraction + 0.01)
        progress.fix(fraction)
        time.sleep(0.1)
    if proc.stdout:
        rest = proc.stdout.read()
        if rest:
            lines.append(rest)
        proc.stdout.close()
    rc = proc.wait()
    if rc != 0:
        return False, f"{CLIP_POSTPROCESS_SCRIPT.name} failed:\n" + "\n".join(lines[-20:])
    progress.fix(1.0)
    return True, str(out_path)


def _has_audio_stream(video_path: str) -> bool:
    ffprobe = find_tool("ffprobe")
    if not ffprobe:
        return True  # assume yes if ffprobe unavailable; let ffmpeg decide
    try:
        proc = subprocess.Popen(
            [ffprobe, "-v", "quiet", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            **hidden_subprocess_kwargs(),
        )
        stdout, _ = proc.communicate(timeout=10)
        return bool(stdout.strip())
    except Exception:
        return True  # assume yes on probe failure; let ffmpeg decide


def export_full_audio_mp3(state: VideoState, out_path: Path, progress: ExportProgress) -> tuple[bool, str]:
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        return False, "ffmpeg not found on PATH"
    if not _has_audio_stream(state.path):
        progress.audio(1.0)
        return True, "No audio stream in source video"
    full_duration = max(1.0 / state.fps, state.total_frames / state.fps)
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats", "-stats_period", "0.1",
        "-i", state.path, "-vn", "-map", "0:a:0?", "-c:a", "libmp3lame", "-q:a", "2", str(out_path),
    ]
    progress.stage("extracting full audio to mp3")
    ok, detail = _run_ffmpeg_with_progress(cmd, full_duration, progress.audio)
    if not ok:
        return False, detail
    if not out_path.exists() or out_path.stat().st_size == 0:
        return False, "No MP3 output created"
    return True, str(out_path)
