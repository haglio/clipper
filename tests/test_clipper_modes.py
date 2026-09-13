"""The two closed sets a session carries, as the words the session file holds."""
from __future__ import annotations

import json

from clipper.loop_modes import LOOP_MODES, LoopMode, read_loop_mode
from clipper.wrap_modes import WrapMode, read_wrap_mode


class TestLoopMode:
    def test_each_entry_is_spelled_as_the_session_files_already_spell_it(self):
        assert {entry.value for entry in LoopMode} == {
            "base-tip-base", "tip-base-tip", "base-tip", "tip-base"}

    def test_the_cycle_walks_the_four_in_the_order_the_button_always_has(self):
        assert LOOP_MODES == (
            LoopMode.BASE_TIP_BASE, LoopMode.TIP_BASE_TIP, LoopMode.BASE_TIP, LoopMode.TIP_BASE)

    def test_an_entry_writes_as_its_word(self):
        assert json.dumps({"loop_mode": LoopMode.TIP_BASE}) == '{"loop_mode": "tip-base"}'
        assert f"--loop-mode {LoopMode.BASE_TIP}" == "--loop-mode base-tip"

    def test_a_known_word_reads_as_its_entry(self):
        assert read_loop_mode("tip-base-tip") is LoopMode.TIP_BASE_TIP
        assert read_loop_mode(LoopMode.BASE_TIP) is LoopMode.BASE_TIP

    def test_a_word_it_does_not_know_reads_as_the_default(self):
        """A session file from another build must still open, in the shape a
        new session starts in."""
        for raw in ("", "sideways", None, 3):
            assert read_loop_mode(raw) is LoopMode.BASE_TIP_BASE


class TestWrapMode:
    def test_the_two_words_are_the_colors_the_version_one_file_holds(self):
        """Evolver enumerates and rewrites these files, and the format is
        unversioned, so the wire word stays the color it always was."""
        assert (WrapMode.OVER_LOADED.value, WrapMode.OVER_ACTIVE.value) == ("blue", "yellow")

    def test_a_known_word_reads_as_its_entry(self):
        assert read_wrap_mode("yellow") is WrapMode.OVER_ACTIVE
        assert read_wrap_mode(WrapMode.OVER_LOADED) is WrapMode.OVER_LOADED

    def test_a_word_it_does_not_know_reads_as_over_the_loaded_range(self):
        """The range a new session wraps within; what the loader used to do with a
        stray word was fall through to the active range, which nothing asked for."""
        for raw in ("red", "", None):
            assert read_wrap_mode(raw) is WrapMode.OVER_LOADED
