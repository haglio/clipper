from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from clipper.clip_postprocess_pipeline import postprocess_clip
    from clipper.export_progress import progress_line
    from clipper.loop_modes import LOOP_MODES
    from clipper.postprocess_options import PostprocessOptions
else:
    from .clip_postprocess_pipeline import postprocess_clip
    from .export_progress import progress_line
    from .loop_modes import LOOP_MODES
    from .postprocess_options import PostprocessOptions


def build_parser() -> argparse.ArgumentParser:
    """The command line, with every default read off ``PostprocessOptions``.

    Including the ones the help text states: ``%(default)s`` quotes the value
    argparse was handed, so there is no second copy to go stale.
    """
    ap = argparse.ArgumentParser(
        description="Normalize clip loop shape, smooth the seam, and shrink the output if needed."
    )
    ap.add_argument("input", help="Input video path")
    ap.add_argument("-o", "--output", required=True, help="Output video path")
    ap.add_argument(
        "--loop-mode",
        choices=LOOP_MODES,
        default=PostprocessOptions.loop_mode,
        help="How to normalize the exported clip before smoothing the seam",
    )
    ap.add_argument(
        "--bridge-ms",
        type=float,
        default=PostprocessOptions.bridge_ms,
        help="Bridge length in milliseconds (default: %(default)s)",
    )
    ap.add_argument(
        "--bridge-frames",
        type=int,
        default=PostprocessOptions.bridge_frames,
        help="Bridge length in frames (overrides --bridge-ms)",
    )
    ap.add_argument(
        "--mode",
        choices=["flow", "blend", "register"],
        default=PostprocessOptions.mode,
        help="Seam smoothing mode: register (align via keypoints, default), flow (optical flow warp), blend (simple crossfade)",
    )
    length_group = ap.add_mutually_exclusive_group()
    length_group.add_argument(
        "--keep-length",
        dest="keep_length",
        action="store_true",
        help="Replace the tail with the bridge instead of appending it (default)",
    )
    length_group.add_argument(
        "--append",
        dest="keep_length",
        action="store_false",
        help="Append the bridge to the end instead of replacing the tail",
    )
    ap.set_defaults(keep_length=PostprocessOptions.keep_length)
    ap.add_argument(
        "--symmetric-blend",
        type=int,
        default=PostprocessOptions.symmetric_blend,
        help="Also softly pull the first/last N frames toward each other before bridge generation",
    )
    ap.add_argument(
        "--seam-ms",
        type=float,
        default=PostprocessOptions.seam_ms,
        help="RIFE seam convergence duration per side in ms, for --mode register only "
             "(default: %(default)s). Set to 0 to disable.",
    )
    ap.add_argument(
        "--copy-audio",
        action="store_true",
        default=PostprocessOptions.copy_audio,
        help="Try to keep input audio (usually not ideal for seamless loops)",
    )
    ap.add_argument(
        "--crf",
        type=int,
        default=PostprocessOptions.crf,
        help="libx264 CRF (default: %(default)s)",
    )
    ap.add_argument(
        "--preset",
        default=PostprocessOptions.preset,
        help="libx264 preset (default: %(default)s)",
    )
    ap.add_argument(
        "--pix-fmt",
        default=PostprocessOptions.pix_fmt,
        help="Output pixel format (default: %(default)s)",
    )
    ap.add_argument(
        "--max-mb",
        type=float,
        default=PostprocessOptions.max_mb,
        help="Maximum output file size in MB (default: %(default)s)",
    )
    return ap


def parse_options(argv: Sequence[str] | None = None) -> PostprocessOptions:
    """The command line as the record the pipeline works from.

    Every flag is a field, so a flag added without one cannot be constructed.
    """
    return PostprocessOptions(**vars(build_parser().parse_args(argv)))


def _say_how_far(fraction: float) -> None:
    """Print how far the run has got, for whoever is driving this as a
    subprocess -- flushed, because the point of it is to arrive while the work
    is still going.
    """
    print(progress_line(fraction), flush=True)


def main():
    summary = postprocess_clip(parse_options(), report=_say_how_far)

    print(f"Input FPS: {summary['fps']:.6f}")
    print(f"Input frames: {summary['input_frames']}")
    print(f"Loop mode: {summary['loop_mode']}")
    print(f"Normalized frames: {summary['normalized_frames']}")
    print(f"Bridge frames: {summary['bridge_frames']}")
    print(f"Output frames: {summary['output_frames']}")
    print(f"Encode attempts: {summary['encode_attempts']}")
    print(f"Final scale: {summary['final_scale']:.4f}")
    print(f"Final size (bytes): {summary['final_size_bytes']}")
    print(f"Target max size (MB): {summary['target_max_mb']:g}")
    print(f"Wrote: {summary['output_path']}")


if __name__ == "__main__":
    main()
