"""Where Clipper puts a cut, held to what Genau says its clips folder holds.

Genau publishes ``genau_contract.json`` at its checkout root.  Neither gate
clones the other, so on a machine with no Genau beside this one there is
nothing to compare and the check says so.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from clipper.paths import clips_dir, library_root, vr_clips_dir

CONTRACT = Path("genau") / "genau_contract.json"
SECTION_BEFORE_THE_RENAME = "inside_the_clips_folder"


def _promise() -> dict | None:
    for parent in Path(__file__).resolve().parents:
        published = parent / CONTRACT
        if published.is_file():
            return json.loads(published.read_text(encoding="utf-8"))
    return None


@pytest.fixture
def inside_the_flicks_folder() -> dict:
    promise = _promise()
    if promise is None:
        pytest.skip(f"no {CONTRACT.as_posix()} beside this checkout")
    return promise.get("inside_the_flicks_folder") or promise[SECTION_BEFORE_THE_RENAME]


def test_a_cut_lands_in_genaus_2d_folder_and_a_vr_cut_in_its_vr_folder(
    inside_the_flicks_folder, content_overlay,
):
    content_overlay({"library_root": "D:/example-suite"})
    genau_flicks = library_root() / "videos" / "genau" / "clips"

    assert clips_dir().parent == genau_flicks / inside_the_flicks_folder["flat"]
    assert vr_clips_dir() == genau_flicks / inside_the_flicks_folder["vr"]
