from __future__ import annotations

import subprocess
import sys
from pathlib import Path


from clipper.clip_postprocess import normalize_loop_mode, shift_frames_halfway


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
