"""``AffirmativeVerdictWord`` — the vocabulary reading a judge's reply as "yes"."""

from __future__ import annotations

from enum import Enum


class AffirmativeVerdictWord(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """Words that make a judge's free-text reply an affirmative verdict.

    String-valued for stable, human-readable serialisation independent of enum
    ordering.

    As with :class:`~pirn_agents.evaluation.negative_verdict_word.NegativeVerdictWord`
    the vocabulary serves two roles: :meth:`leading_tokens` is matched against
    the reply's first token, while :meth:`scan_markers` is the narrower subset
    safe to match as a substring anywhere in the reply. Affirmative markers are
    only consulted *after* the negative ones, so a reply like "not supported"
    reads as a negative verdict.

    Members
    -------
    YES:
        The bare affirmation — the most common leading token, and also a safe
        substring marker.
    TRUE:
        The boolean spelling of an affirmative verdict.
    ONE:
        The numeric spelling of an affirmative verdict.
    SUPPORTED:
        The claim is backed by the supplied context.
    RELEVANT:
        The retrieved context bears on the question.
    FAITHFUL:
        The answer stays within the supplied context.
    CORRECT:
        The answer is right on the merits.
    ATTRIBUTED:
        The claim is traceable to a specific passage.
    """

    YES = "yes"
    TRUE = "true"
    ONE = "1"
    SUPPORTED = "supported"
    RELEVANT = "relevant"
    FAITHFUL = "faithful"
    CORRECT = "correct"
    ATTRIBUTED = "attributed"

    @classmethod
    def leading_tokens(cls) -> frozenset[str]:
        """Return the single-word values matched against a reply's first token."""
        return frozenset(member.value for member in cls if " " not in member.value)

    @classmethod
    def scan_markers(cls) -> tuple[str, ...]:
        """Return the values safe to match as a substring anywhere in a reply."""
        return (cls.SUPPORTED.value, cls.RELEVANT.value, cls.FAITHFUL.value, cls.YES.value)
