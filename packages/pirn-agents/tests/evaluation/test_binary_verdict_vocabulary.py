"""Characterisation tests for the :class:`BinaryVerdictParser` vocabularies.

Pins the exact word lists and the two-stage matching contract (leading token
first, then substring markers with negative precedence) so hoisting the inline
set/tuple literals onto :class:`NegativeVerdictWord` / :class:`AffirmativeVerdictWord`
is provably behaviour-preserving.
"""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.affirmative_verdict_word import AffirmativeVerdictWord
from pirn_agents.evaluation.binary_verdict_parser import BinaryVerdictParser
from pirn_agents.evaluation.negative_verdict_word import NegativeVerdictWord


class TestLeadingTokenVocabulary(unittest.TestCase):
    def test_every_negative_leading_token_reads_false(self) -> None:
        # Arrange: the full negative leading-token vocabulary.
        parser = BinaryVerdictParser()

        # Act / Assert: each one, as the leading token, fails the verdict.
        for word in (
            "no",
            "not",
            "false",
            "0",
            "unsupported",
            "irrelevant",
            "unfaithful",
            "incorrect",
        ):
            with self.subTest(word=word):
                assert parser.parse(f"{word}, per the passage") is False

    def test_every_affirmative_leading_token_reads_true(self) -> None:
        # Arrange: the full affirmative leading-token vocabulary.
        parser = BinaryVerdictParser()

        # Act / Assert: each one, as the leading token, passes the verdict.
        for word in (
            "yes",
            "true",
            "1",
            "supported",
            "relevant",
            "faithful",
            "correct",
            "attributed",
        ):
            with self.subTest(word=word):
                assert parser.parse(f"{word}, per the passage") is True

    def test_leading_token_is_stripped_of_punctuation_and_case(self) -> None:
        # Arrange / Act / Assert: trailing punctuation and case do not defeat the match.
        parser = BinaryVerdictParser()
        assert parser.parse('  "YES."  ') is True
        assert parser.parse("No!") is False

    def test_leading_token_wins_over_later_markers(self) -> None:
        # Arrange / Act / Assert: a leading negative short-circuits an affirmative marker.
        parser = BinaryVerdictParser()
        assert parser.parse("No doubt this is supported") is False


class TestSubstringMarkerVocabulary(unittest.TestCase):
    def test_negative_markers_take_precedence_over_affirmative(self) -> None:
        # Arrange / Act / Assert: "not supported" beats the "supported" it contains.
        parser = BinaryVerdictParser()
        assert parser.parse("The claim is not supported by the passage") is False
        assert parser.parse("The claim is unsupported here") is False
        assert parser.parse("The claim is irrelevant but supported") is False

    def test_affirmative_markers_match_anywhere(self) -> None:
        # Arrange / Act / Assert: each affirmative marker fires from mid-sentence.
        parser = BinaryVerdictParser()
        for marker in ("supported", "relevant", "faithful", "yes"):
            with self.subTest(marker=marker):
                assert parser.parse(f"I would say {marker} on balance") is True

    def test_non_marker_negative_words_do_not_scan_as_substrings(self) -> None:
        # Arrange: "incorrect"/"unfaithful"/"false" are leading tokens only — they
        # are deliberately NOT part of the substring scan, so an affirmative
        # marker still wins when they appear mid-sentence.
        parser = BinaryVerdictParser()

        # Act / Assert
        assert parser.parse("The wording is incorrect but the claim is supported") is True
        assert parser.parse("It reads unfaithful, though relevant") is True
        assert parser.parse("A false start, yet faithful overall") is True

    def test_no_recognisable_signal_fails_closed(self) -> None:
        # Arrange / Act / Assert
        parser = BinaryVerdictParser()
        assert parser.parse("maybe, hard to say") is False
        assert parser.parse("") is False
        assert parser.parse("   ") is False


class TestVocabularyEnums(unittest.TestCase):
    def test_enum_values_are_plain_strings(self) -> None:
        # Arrange / Act / Assert: the str mixin keeps `==` against raw literals working.
        assert NegativeVerdictWord.UNSUPPORTED == "unsupported"
        assert AffirmativeVerdictWord.SUPPORTED == "supported"

    def test_leading_tokens_match_the_historical_sets(self) -> None:
        # Arrange / Act / Assert: byte-identical to the hoisted set literals.
        assert NegativeVerdictWord.leading_tokens() == frozenset(
            {"no", "not", "false", "0", "unsupported", "irrelevant", "unfaithful", "incorrect"}
        )
        assert AffirmativeVerdictWord.leading_tokens() == frozenset(
            {"yes", "true", "1", "supported", "relevant", "faithful", "correct", "attributed"}
        )

    def test_scan_markers_match_the_historical_tuples(self) -> None:
        # Arrange / Act / Assert: byte-identical to the hoisted marker tuples.
        assert NegativeVerdictWord.scan_markers() == ("not supported", "unsupported", "irrelevant")
        assert AffirmativeVerdictWord.scan_markers() == (
            "supported",
            "relevant",
            "faithful",
            "yes",
        )

    def test_multiword_phrase_is_not_a_leading_token(self) -> None:
        # Arrange / Act / Assert: "not supported" can never be a single leading token,
        # so it is excluded from the leading-token set it would otherwise pollute.
        assert NegativeVerdictWord.NOT_SUPPORTED == "not supported"
        assert "not supported" not in NegativeVerdictWord.leading_tokens()


if __name__ == "__main__":
    unittest.main()
