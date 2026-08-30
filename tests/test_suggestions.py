"""Tests for clipper.suggestions — the marks the app offers, and what it compares against."""
from __future__ import annotations

from clipper.suggestions import Suggestions


class TestMoved:
    def test_a_mark_still_where_the_session_opened_it_has_not_moved(self):
        marks = Suggestions(initial_start=10, initial_end=40)

        assert marks.moved(10, 40) == (False, False)

    def test_each_mark_is_judged_on_its_own(self):
        marks = Suggestions(initial_start=10, initial_end=40)

        assert marks.moved(12, 40) == (True, False)
        assert marks.moved(10, 38) == (False, True)

    def test_a_session_with_no_opening_selection_has_nothing_to_have_moved_from(self):
        marks = Suggestions()

        assert marks.moved(12, 38) == (False, False)


class TestOffer:
    def test_a_new_pair_is_taken_and_reported(self):
        marks = Suggestions()

        assert marks.offer(12, 38) is True
        assert (marks.suggested_in, marks.suggested_out) == (12, 38)

    def test_the_pair_it_already_holds_is_not_a_change(self):
        marks = Suggestions(suggested_in=12, suggested_out=38)

        assert marks.offer(12, 38) is False

    def test_half_a_change_is_a_change(self):
        marks = Suggestions(suggested_in=12, suggested_out=38)

        assert marks.offer(12, 39) is True
        assert marks.suggested_out == 39

    def test_withdrawing_both_marks_is_a_change(self):
        marks = Suggestions(suggested_in=12, suggested_out=38)

        assert marks.offer(None, None) is True
        assert (marks.suggested_in, marks.suggested_out) == (None, None)
