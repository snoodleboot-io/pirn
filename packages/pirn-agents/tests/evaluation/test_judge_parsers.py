"""Tests for the judge free-text parsers (S4).

The parsers used to answer whatever they were handed: no number scored ``0.0``,
no A/B token returned ``"tie"``, ``"On a 1-5 scale: 4"`` scored a perfect
``1.0``, and ``lowered.find("a")`` read a vote for A out of any reply containing
the letter. Every one of those put a fabricated measurement into an evaluation
report (PIR-873), so the cases below pin both halves: what a readable reply
means, and that an unreadable one raises instead of scoring.
"""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.judge_score_parser import JudgeScoreParser
from pirn_agents.evaluation.pairwise_choice_parser import PairwiseChoiceParser
from pirn_agents.exceptions.unreadable_judge_reply_error import UnreadableJudgeReplyError


class ParseJudgeScoreTests(unittest.TestCase):
    def test_reads_a_bare_unit_interval_number(self) -> None:
        assert JudgeScoreParser().parse("0.8") == 0.8

    def test_reads_the_bounds(self) -> None:
        assert JudgeScoreParser().parse("0") == 0.0
        assert JudgeScoreParser().parse("1.0") == 1.0

    def test_reads_a_labelled_number(self) -> None:
        assert JudgeScoreParser().parse("Score: 0.5") == 0.5
        assert JudgeScoreParser().parse("rating = .25") == 0.25

    def test_tolerates_surrounding_whitespace_and_a_full_stop(self) -> None:
        assert JudgeScoreParser().parse("  0.75.\n") == 0.75

    def test_a_mid_range_rating_on_another_scale_is_not_scored_perfect(self) -> None:
        """The headline defect: the leading ``1`` of the scale became the score."""
        with self.assertRaises(UnreadableJudgeReplyError):
            JudgeScoreParser().parse("On a 1-5 scale: 4")

    def test_a_ten_point_rating_is_unreadable_rather_than_rescaled(self) -> None:
        with self.assertRaises(UnreadableJudgeReplyError):
            JudgeScoreParser().parse("7 out of 10")

    def test_a_number_outside_the_unit_interval_is_unreadable_not_clamped(self) -> None:
        for reply in ("100", "-0.5", "4"):
            with self.subTest(reply=reply), self.assertRaises(UnreadableJudgeReplyError):
                JudgeScoreParser().parse(reply)

    def test_prose_around_the_number_is_unreadable(self) -> None:
        with self.assertRaises(UnreadableJudgeReplyError):
            JudgeScoreParser().parse("Score: 0.5 because the answer omits the caveat")

    def test_no_number_raises_instead_of_scoring_zero(self) -> None:
        for reply in ("", "excellent", "I cannot help with that request."):
            with self.subTest(reply=reply), self.assertRaises(UnreadableJudgeReplyError):
                JudgeScoreParser().parse(reply)

    def test_the_error_names_what_was_expected_and_does_not_dump_a_long_reply(self) -> None:
        long_reply = "x" * 500
        with self.assertRaises(UnreadableJudgeReplyError) as caught:
            JudgeScoreParser().parse(long_reply)
        assert "0.0, 1.0" in str(caught.exception)
        assert len(str(caught.exception)) < 250

    def test_non_str_raises(self) -> None:
        with self.assertRaises(TypeError):
            JudgeScoreParser().parse(1)  # type: ignore[arg-type]


class ParsePairwiseChoiceTests(unittest.TestCase):
    def test_reads_a_bare_choice(self) -> None:
        assert PairwiseChoiceParser().parse("A") == "a"
        assert PairwiseChoiceParser().parse("b.") == "b"

    def test_reads_a_choice_in_a_sentence(self) -> None:
        assert PairwiseChoiceParser().parse("A is better") == "a"
        assert PairwiseChoiceParser().parse("B, clearly") == "b"
        assert PairwiseChoiceParser().parse("Response B answers the prompt") == "b"

    def test_reads_a_tie(self) -> None:
        assert PairwiseChoiceParser().parse("tie") == "tie"
        assert PairwiseChoiceParser().parse("It's a tie") == "tie"
        assert PairwiseChoiceParser().parse("A and B are equally good") == "tie"
        assert PairwiseChoiceParser().parse("Neither is better") == "tie"

    def test_the_english_article_is_not_a_vote_for_a(self) -> None:
        """``lowered.find("a")`` used to read this reply — a vote for B — as A."""
        assert PairwiseChoiceParser().parse("B is a better answer") == "b"

    def test_a_letter_inside_a_word_is_not_a_tie(self) -> None:
        """``"equal" in lowered`` fired on any word containing it."""
        assert PairwiseChoiceParser().parse("B states it more equably") == "b"

    def test_an_answer_label_is_not_read_as_its_own_letters(self) -> None:
        """``"Answer: B"`` scored for A: its ``a`` comes before its ``b``."""
        assert PairwiseChoiceParser().parse("Answer: B") == "b"

    def test_an_empty_reply_raises_instead_of_returning_tie(self) -> None:
        for reply in ("", "   "):
            with self.subTest(reply=reply), self.assertRaises(UnreadableJudgeReplyError):
                PairwiseChoiceParser().parse(reply)

    def test_a_reply_naming_no_verdict_raises(self) -> None:
        with self.assertRaises(UnreadableJudgeReplyError):
            PairwiseChoiceParser().parse("I cannot help with that request.")

    def test_a_reply_naming_both_without_a_tie_word_raises(self) -> None:
        with self.assertRaises(UnreadableJudgeReplyError):
            PairwiseChoiceParser().parse("A is more precise, B is more complete")

    def test_non_str_raises(self) -> None:
        with self.assertRaises(TypeError):
            PairwiseChoiceParser().parse(1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
