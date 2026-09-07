from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from clipper.clip_postprocess import main, parse_options
from clipper.clip_postprocess_transforms import normalize_loop_mode, shift_frames_halfway
from clipper.postprocess_options import PostprocessOptions


class TestShiftFramesHalfway:
    def test_rotates_sequence_from_middle(self, frames_of, values_of):
        frames = frames_of([1, 2, 3, 4])
        assert values_of(shift_frames_halfway(frames)) == [3, 4, 1, 2]


class TestNormalizeLoopMode:
    def test_base_tip_base_is_unchanged(self, frames_of, values_of):
        frames = frames_of([1, 2, 3, 2, 1])
        assert values_of(normalize_loop_mode(frames, "base-tip-base")) == [1, 2, 3, 2, 1]

    def test_tip_base_tip_rotates_by_half(self, frames_of, values_of):
        frames = frames_of([5, 4, 3, 2, 1, 2])
        assert values_of(normalize_loop_mode(frames, "tip-base-tip")) == [2, 1, 2, 5, 4, 3]

    def test_base_tip_appends_reversed_tail_without_duplicate_tip(self, frames_of, values_of):
        frames = frames_of([1, 2, 3])
        assert values_of(normalize_loop_mode(frames, "base-tip")) == [1, 2, 3, 2, 1]

    def test_tip_base_prepends_reversed_head_without_duplicate_tip(self, frames_of, values_of):
        frames = frames_of([3, 2, 1])
        assert values_of(normalize_loop_mode(frames, "tip-base")) == [1, 2, 3, 2, 1]


class TestTheDefaultsHaveOneHome:
    """The record holds them; the parser reads them off it.

    A default written in the parser and again in the pipeline's getattr
    fallback is two places to change it, and the two would have gone apart the
    first time either moved.
    """

    def test_a_command_line_with_no_flags_is_the_records_own_defaults(self):
        parsed = parse_options(["clip in.mp4", "-o", "clip out.mp4"])

        assert parsed == PostprocessOptions(input="clip in.mp4", output="clip out.mp4")

    def test_every_flag_the_parser_takes_reaches_the_pipeline(self):
        """A flag the record has no field for cannot be constructed at all."""
        parsed = parse_options([
            "clip in.mp4", "-o", "clip out.mp4", "--loop-mode", "base-tip",
            "--bridge-ms", "120", "--bridge-frames", "4", "--mode", "flow",
            "--append", "--symmetric-blend", "3", "--seam-ms", "0",
            "--copy-audio", "--crf", "20", "--preset", "veryfast",
            "--pix-fmt", "yuv444p", "--max-mb", "2.5",
        ])

        assert parsed == PostprocessOptions(
            input="clip in.mp4", output="clip out.mp4", loop_mode="base-tip",
            bridge_ms=120.0, bridge_frames=4, mode="flow", keep_length=False,
            symmetric_blend=3, seam_ms=0.0, copy_audio=True, crf=20,
            preset="veryfast", pix_fmt="yuv444p", max_mb=2.5,
        )

    def test_the_help_text_quotes_the_default_rather_than_repeating_it(self, capsys):
        """--seam-ms's stated default is the record's, not a third copy."""
        with pytest.raises(SystemExit):
            parse_options(["--help"])

        printed = capsys.readouterr().out
        assert f"default: {PostprocessOptions.seam_ms}" in printed


def test_clip_postprocess_cli_runs_as_direct_script():
    script_path = Path(__file__).resolve().parent.parent / "clipper" / "clip_postprocess.py"
    result = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Normalize clip loop shape" in result.stdout
    assert "register" in result.stdout


def test_the_cli_runs_a_clip_through_and_prints_what_it_wrote(tmp_path, frames_of, capsys):
    """One real invocation, not just --help.

    ffmpeg and the decoder are stubbed; everything between them -- argument
    parsing, loop normalization, the bridge, the size loop and the summary the
    user reads -- runs for real.
    """
    output = tmp_path / "cli_out.mp4"

    def fake_encode(frames, fps, out_path, *args, **kwargs):
        Path(out_path).write_bytes(b"\0" * 32)

    argv = [
        "clip_postprocess", str(tmp_path / "cli_in.mp4"), "-o", str(output),
        "--loop-mode", "base-tip", "--mode", "blend", "--bridge-frames", "1",
        "--seam-ms", "0",
    ]
    with patch.object(sys, "argv", argv), \
         patch("clipper.clip_postprocess_pipeline.ffprobe_video",
               return_value={"fps": 24.0, "width": 8, "height": 8,
                             "nb_frames": 4, "duration": 4 / 24.0}), \
         patch("clipper.clip_postprocess_pipeline.read_frames",
               return_value=frames_of([10, 20, 30, 40], size=8)), \
         patch("clipper.clip_postprocess_pipeline.encode_with_ffmpeg", fake_encode):
        main()

    printed = capsys.readouterr().out
    assert "Input FPS: 24.000000" in printed
    assert "Input frames: 4" in printed
    assert "Loop mode: base-tip" in printed
    assert "Normalized frames: 7" in printed
    assert "Bridge frames: 1" in printed
    assert "Output frames: 7" in printed
    assert "Encode attempts: 1" in printed
    assert "Final size (bytes): 32" in printed
    assert f"Wrote: {output}" in printed
    assert output.exists()
