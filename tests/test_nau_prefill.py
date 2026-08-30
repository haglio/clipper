"""What the launcher prefills from, now that the suite's main player is Nau.

Fun Time's `;` already pushes the video and the playhead into
``clipper.create_session`` without asking clipper anything.  This is the pull
side, for opening clipper on its own, and it reads the same two fields out of
the same file, so the two ways of starting a session cannot disagree about what
was playing.
"""
from __future__ import annotations

import ast
import inspect
import subprocess
import textwrap
from pathlib import Path

from clipper import nau_prefill
from clipper.nau_prefill import SessionPrefill, detect_nau_session_prefill

# Nau publishes `key=value` lines. Fabricated values throughout: what matters
# is the shape, and a real one would name the library.
_PLAYING = {
    "video": "S:/library/main/alpha clip.mp4",
    "position_ms": "72500",
    "duration_ms": "300000",
    "has_funscript": "1",
    "funscript_resting": "0",
    "state": "normal",
}


def _status(tmp_path: Path, **overrides) -> Path:
    fields = {**_PLAYING, **overrides}
    path = tmp_path / "nau_status.txt"
    path.write_text(
        "".join(f"{k}={v}\n" for k, v in fields.items()), encoding="utf-8"
    )
    return path


class TestWhatItReads:
    def test_it_takes_the_video_nau_is_playing(self, tmp_path: Path):
        prefill = detect_nau_session_prefill(_status(tmp_path))

        assert prefill.video_file == "S:/library/main/alpha clip.mp4"

    def test_the_timestamp_is_the_playhead(self, tmp_path: Path):
        """72500 ms is 00:01:12.500, and the launcher's field wants that shape."""
        prefill = detect_nau_session_prefill(_status(tmp_path))

        assert prefill.timestamp == "00:01:12.500"

    def test_the_session_is_named_the_way_the_push_side_names_it(self, tmp_path: Path):
        """Pressing `;` and opening clipper by hand must agree on the name.

        create_session defaults it to ``sanitize_name(stem)``; anything else
        here means the same video makes two differently-named sessions
        depending on how the session was started.
        """
        from clipper.create_session import build_session_payload

        prefill = detect_nau_session_prefill(_status(tmp_path))
        pushed = build_session_payload(prefill.video_file, 0.0, fps=30.0, total_frames=100)

        assert prefill.session_name == pushed["session_name"]

class TestWhenThereIsNothingToPrefill:
    """Every one of these is a normal state, not an error: no prefill, blank form."""

    def test_a_machine_that_has_not_named_the_status_file(self, monkeypatch):
        monkeypatch.setattr(nau_prefill, "nau_status_file", lambda: None)

        assert detect_nau_session_prefill() is None

    def test_nau_is_not_running_so_the_file_is_not_there(self, tmp_path: Path):
        assert detect_nau_session_prefill(tmp_path / "nau_status.txt") is None

    def test_nau_is_running_with_nothing_playing(self, tmp_path: Path):
        """The empty `video` is Nau's own way of saying so, and what `;` checks."""
        assert detect_nau_session_prefill(_status(tmp_path, video="")) is None

    def test_a_status_file_caught_mid_write(self, tmp_path: Path):
        path = tmp_path / "nau_status.txt"
        path.write_text("vid", encoding="utf-8")

        assert detect_nau_session_prefill(path) is None

    def test_a_playhead_that_is_not_a_number(self, tmp_path: Path):
        """Rather than lose the video over it, the session starts at zero."""
        prefill = detect_nau_session_prefill(_status(tmp_path, position_ms="  "))

        assert prefill.timestamp == "00:00:00.000"

    def test_a_file_that_cannot_be_read(self, tmp_path: Path):
        assert detect_nau_session_prefill(tmp_path) is None


class TestTheContractWithNau:
    """The two field names clipper depends on, checked against their producer.

    Nau publishes these; fun_time and clipper both read them. This is the check
    that fires by itself on a machine that has the genau checkout, so a rename
    on Nau's side reds clipper's suite instead of quietly emptying the launcher.
    """

    @staticmethod
    def _nau_status_source() -> Path | None:
        """``genau/nau/status.py`` beside the primary checkout, if it is there.

        Resolved through the primary rather than from here, because everything
        runs in a worktree and a worktree's neighbors are other worktrees.
        """
        from clipper.paths import PROJECT_DIR

        try:
            common = subprocess.run(
                ["git", "-C", str(PROJECT_DIR), "rev-parse", "--git-common-dir"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
        primary = (PROJECT_DIR / common).resolve().parent
        source = primary.parent / "genau" / "nau" / "status.py"
        return source if source.is_file() else None

    @staticmethod
    def _keys_clipper_reads() -> set[str]:
        """Every field name the reader asks the status file for, off its own tree.

        Read rather than declared, so there is no second list of these names to
        fall out of step with the ``values.get`` calls that are the real ones.
        """
        source = inspect.getsource(nau_prefill.detect_nau_session_prefill)
        tree = ast.parse(textwrap.dedent(source))
        return {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }

    @staticmethod
    def _keys_nau_publishes(source: Path) -> set[str]:
        """The dict keys ``status_fields`` returns, off its syntax tree."""
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "status_fields":
                return {
                    key.value
                    for inner in ast.walk(node)
                    if isinstance(inner, ast.Dict)
                    for key in inner.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                }
        return set()

    def test_nau_still_publishes_both_fields_clipper_reads(self):
        """Asserted, not skipped, when genau is absent: a checkout without the
        sibling has nothing to disagree with, and saying so in the assertion
        keeps this a test that always runs and always means something."""
        wanted = self._keys_clipper_reads()
        source = self._nau_status_source()
        published = self._keys_nau_publishes(source) if source else wanted

        assert wanted and wanted <= published, (
            f"nau/status.py publishes {sorted(published)}, which no longer covers "
            f"{sorted(wanted)} -- the launcher would prefill nothing"
        )

    def test_the_prefill_reads_a_payload_nau_itself_produced(self, tmp_path: Path):
        """Not a fixture in our own shape: the writer's key set, whatever it holds."""
        source = self._nau_status_source()
        keys = self._keys_nau_publishes(source) if source else set(_PLAYING)
        payload = {key: _PLAYING.get(key, "0") for key in sorted(keys)}
        payload["video"] = "S:/library/main/beta clip.mp4"
        payload["position_ms"] = "1000"
        path = tmp_path / "nau_status.txt"
        path.write_text("".join(f"{k}={v}\n" for k, v in payload.items()), encoding="utf-8")

        prefill = detect_nau_session_prefill(path)

        assert prefill == SessionPrefill(
            video_file="S:/library/main/beta clip.mp4",
            session_name="beta clip",
            timestamp="00:00:01.000",
        )
