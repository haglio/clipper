"""The content overlay: one read, however many modules ask for it."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from clipper.content import load_content


@pytest.fixture(autouse=True)
def _forget_what_was_read():
    """Drop what this test cached: the cache outlives the test that filled it."""
    yield
    load_content.cache_clear()


def _overlay(tmp_path: Path, suite_root: str) -> tuple[Path, Path]:
    """A local overlay and the committed example beside it, both fabricated."""
    local = tmp_path / "content.local.json"
    local.write_text(json.dumps({"suite_root": suite_root}), encoding="utf-8")
    example = tmp_path / "content.example.json"
    example.write_text(
        json.dumps({"suite_root": "C:/path/to/suite-root"}), encoding="utf-8"
    )
    return local, example


class TestTheFileIsReadOnce:
    """Every consumer reads the overlay through here, and several read it per
    call now that no module freezes it at import.  The file is small, but it is
    on the machine's disk and one of those callers runs on every keystroke in
    the launcher's video field, so what is cached is the text it holds.
    """

    def test_a_later_caller_gets_what_the_first_one_read(self, tmp_path: Path):
        local, example = _overlay(tmp_path, "D:/example-suite")
        first = load_content(local, example)

        local.write_text(json.dumps({"suite_root": "E:/other-suite"}), encoding="utf-8")

        assert load_content(local, example) == first

    def test_clearing_the_cache_reads_the_file_again(self, tmp_path: Path):
        local, example = _overlay(tmp_path, "D:/example-suite")
        load_content(local, example)

        local.write_text(json.dumps({"suite_root": "E:/other-suite"}), encoding="utf-8")
        load_content.cache_clear()

        assert load_content(local, example)["suite_root"] == "E:/other-suite"

    def test_each_caller_gets_a_dictionary_of_its_own(self, tmp_path: Path):
        """The text is cached, not the parse.  Handing every caller the same
        dictionary would make one module's edit of it every module's edit.
        """
        local, example = _overlay(tmp_path, "D:/example-suite")

        load_content(local, example)["suite_root"] = "somewhere else entirely"

        assert load_content(local, example)["suite_root"] == "D:/example-suite"


class TestWhichFileAnswers:
    def test_the_local_overlay_answers_when_there_is_one(self, tmp_path: Path):
        local, example = _overlay(tmp_path, "D:/example-suite")

        assert load_content(local, example)["suite_root"] == "D:/example-suite"

    def test_the_committed_example_answers_when_there_is_not(self, tmp_path: Path):
        _local, example = _overlay(tmp_path, "D:/example-suite")

        content = load_content(tmp_path / "absent.json", example)

        assert content["suite_root"] == "C:/path/to/suite-root"
