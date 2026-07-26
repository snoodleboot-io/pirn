"""``NegativeVerdictWord`` — the vocabulary reading a judge's reply as "no"."""

from __future__ import annotations

from enum import Enum


class NegativeVerdictWord(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """Words and phrases that make a judge's free-text reply a negative verdict.

    String-valued for stable, human-readable serialisation independent of enum
    ordering.

    The vocabulary serves two distinct roles, and they are deliberately *not*
    the same set. :meth:`leading_tokens` is matched against the reply's first
    token only; :meth:`scan_markers` is the narrower subset safe to match as a
    substring anywhere in the reply, because scanning for e.g. ``NO`` or ``NOT``
    would misread ordinary words like "know" or "cannot".

    Members
    -------
    NO:
        The bare refusal — by far the most common leading token.
    NOT:
        A leading negation, as in "not in the context".
    FALSE:
        The boolean spelling of a negative verdict.
    ZERO:
        The numeric spelling of a negative verdict.
    UNSUPPORTED:
        The claim is not backed by the supplied context.
    IRRELEVANT:
        The retrieved context does not bear on the question.
    UNFAITHFUL:
        The answer departs from the supplied context.
    INCORRECT:
        The answer is wrong on the merits.
    NOT_SUPPORTED:
        The two-word phrase, scanned as a substring so it takes precedence over
        the ``"supported"`` it contains. Being multi-word it can never be a
        leading token, and :meth:`leading_tokens` excludes it.
    """

    NO = "no"
    NOT = "not"
    FALSE = "false"
    ZERO = "0"
    UNSUPPORTED = "unsupported"
    IRRELEVANT = "irrelevant"
    UNFAITHFUL = "unfaithful"
    INCORRECT = "incorrect"
    NOT_SUPPORTED = "not supported"

    @classmethod
    def leading_tokens(cls) -> frozenset[str]:
        """Return the single-word values matched against a reply's first token."""
        return frozenset(member.value for member in cls if " " not in member.value)

    @classmethod
    def scan_markers(cls) -> tuple[str, ...]:
        """Return the values safe to match as a substring anywhere in a reply."""
        return (cls.NOT_SUPPORTED.value, cls.UNSUPPORTED.value, cls.IRRELEVANT.value)
