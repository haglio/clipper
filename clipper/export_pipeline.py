"""The three steps an export runs, and where each one writes.

Off the Qt thread and with no Qt in it: the sequence, the output paths and what
a failed step means used to live inside ``ExportWorker.run``, so the only way
to ask any of it was to build a QThread.  The worker calls this and turns the
answer into its finished signal.
"""

from __future__ import annotations

from pathlib import Path

from . import export_steps
from .export_progress import ExportProgress
from .paths import RAW_CLIPS_DIR, audio_dir, clips_dir, sanitize_name, vr_clips_dir
from .sidecar import record_provenance
from .state import VideoState


def _output_paths(state: VideoState) -> tuple[Path, Path, Path]:
    """The raw clip, the finished clip and the mp3, all named for the session.

    The clip goes to genau's VR folder or its flat one, which is what the
    launcher's checkbox decided when the session was made.
    """
    session_base = sanitize_name(state.session_name)
    clip_folder = vr_clips_dir() if state.vr else clips_dir()
    return (
        RAW_CLIPS_DIR / f"{session_base}.mp4",
        clip_folder / f"{session_base}.mp4",
        audio_dir() / f"{session_base}.mp3",
    )


def run_export(state: VideoState, progress: ExportProgress) -> tuple[bool, str]:
    """Cut the clip, smooth its loop and pull the audio, saying how each goes.

    Answers the way each step does: whether it worked, and the clip it wrote or
    the reason it did not.  A step that raises answers the same way, since the
    caller is a thread and an exception out of it reaches nobody.
    """
    progress.stage("preparing export")
    progress.clip(0.0)
    progress.fix(0.0)
    progress.audio(0.0)

    raw_path, clip_path, audio_path = _output_paths(state)
    try:
        # A whole-video export is already a loop, so it skips the seam pass --
        # and with nothing to post-process, the clip is cut straight to where
        # the post-process would have put it.
        first_output = clip_path if state.skip_postprocess else raw_path
        ok, detail = export_steps.export_raw_clip(state, first_output, progress)
        if not ok:
            return False, detail

        if state.skip_postprocess:
            record_provenance(clip_path)
            progress.fix(1.0)
        else:
            ok, detail = export_steps.run_clip_postprocess(
                state, raw_path, clip_path, progress
            )
            if not ok:
                return False, detail

        ok, detail = export_steps.export_full_audio_mp3(state, audio_path, progress)
        if not ok:
            return False, detail

        return True, f"Done: {clip_path}"
    except Exception as exc:
        return False, str(exc)
