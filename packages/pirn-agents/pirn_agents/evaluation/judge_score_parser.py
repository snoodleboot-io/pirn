"""``JudgeScoreParser`` — read a 0..1 score from a judge reply, or fail.

The rubric prompt asks the judge for "just the number" on a ``0.0``-``1.0``
scale, so that is exactly what this parser accepts.

It used to take the *first* numeric token anywhere in the reply, rescale
``(1, 10]`` by dividing by ten, clamp anything larger to ``1.0``, and score a
reply with no number at all ``0.0`` (PIR-873). Every one of those invented a
measurement:

* ``"On a 1-5 scale: 4"`` read the ``1`` and scored a **perfect 1.0** — the
  worst possible reading of a mid-range rating;
* ``"Reviewed 3 sources; quality is poor"`` scored ``0.3``;
* a refusal, an error string or a provider outage scored ``0.0``, which is a
  real score and appears in a report as one.

A harness whose whole output is numbers cannot be allowed to fabricate them, so
an unreadable reply now raises
:class:`~pirn_agents.exceptions.unreadable_judge_reply_error.UnreadableJudgeReplyError`
and the evaluation fails loudly.

Algorithm:
    1. Reject a non-``str``.
    2. Match the *whole* reply against one number, optionally introduced by a
       ``score:``/``score =`` label and optionally followed by a single ``.``
       or ``!``. Anything else — a second number, prose around it, an empty
       reply — is unreadable.
    3. The number must already lie in ``[0.0, 1.0]``; a value outside it is a
       reply on a different scale than the one asked for, which cannot be
       rescaled without guessing, so it is unreadable too.

Math:
    $$
    \\text{score} = v \\quad \\text{iff } 0 \\leq v \\leq 1
    $$

    No clamping and no rescaling: both silently turn a reply about a different
    scale into a confident number.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

import re
from typing import ClassVar

from pirn_agents.exceptions.unreadable_judge_reply_error import UnreadableJudgeReplyError


class JudgeScoreParser:
    """Read the ``[0, 1]`` score a judge reply states, or raise."""

    #: The whole reply: one number, an optional ``score:`` label, optional
    #: terminal punctuation. Anchored on both ends deliberately — an unanchored
    #: search is what read ``1`` out of ``"On a 1-5 scale: 4"``.
    _score: ClassVar[re.Pattern[str]] = re.compile(
        r"""\A\s*
            (?:(?:score|rating)\s*[:=]\s*)?
            (?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+))
            \s*[.!]?\s*\Z""",
        re.IGNORECASE | re.VERBOSE,
    )

    #: Named in every ``UnreadableJudgeReplyError`` this parser raises.
    _expected: ClassVar[str] = "a single number in [0.0, 1.0], as the whole reply"

    def parse(self, text: str) -> float:
        """Return the score ``text`` states.

        Args:
            text: The judge's reply text.

        Returns:
            The stated score, in ``[0.0, 1.0]``.

        Raises:
            TypeError: If ``text`` is not a ``str``.
            UnreadableJudgeReplyError: If the reply is not a single number in
                ``[0.0, 1.0]``. Never a fabricated ``0.0``.
        """
        if not isinstance(text, str):
            raise TypeError(f"JudgeScoreParser: text must be a str, got {type(text).__name__}")
        match = type(self)._score.match(text)
        if match is None:
            raise UnreadableJudgeReplyError(text, expected=type(self)._expected)
        value = float(match.group("value"))
        if not 0.0 <= value <= 1.0:
            raise UnreadableJudgeReplyError(text, expected=type(self)._expected)
        return value
