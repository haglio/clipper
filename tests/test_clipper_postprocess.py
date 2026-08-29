from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


from clipper.clip_postprocess import main
from clipper.clip_postprocess_transforms import normalize_loop_mode, shift_frames_halfway


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
