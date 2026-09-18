"""``PairwiseChoiceParser`` — read an A/B/tie verdict from a judge reply, or fail.

The pairwise prompt asks the judge to "reply with 'A', 'B', or 'tie'", so that is
what this parser accepts. The verdict refers to *presentation order* (the
response shown first is ``"a"``); the caller maps it back to the real responses
so position bias can be controlled.

It used to answer with substring matching and a fabricated default (PIR-873):

* ``any(marker in lowered for marker in ("tie", "equal", ...))`` fired on any
  reply *containing* those letters, so ``"B states it more equably"`` — and
  anything mentioning "both" — was read as a tie;
* the fallback ``lowered.find("a")`` matched **any letter a anywhere**, so
  ``"Answer: B"`` scored for **A** (its ``a`` is at index 0, before the ``b``);
* an empty or unreadable reply returned ``"tie"``, a real verdict that lands in
  a report as one.

Now: tie words are matched on word boundaries, an ``A``/``B`` verdict is matched
as a standalone capital letter (so the English article ``a`` cannot be mistaken
for a vote) or as an explicit ``response a`` label, and a reply naming neither —
or naming both A and B with no tie word — raises
:class:`~pirn_agents.exceptions.unreadable_judge_reply_error.UnreadableJudgeReplyError`.

Algorithm:
    1. Reject a non-``str``; an empty reply is unreadable.
    2. A bare ``a`` / ``b`` reply (any case, surrounding punctuation stripped)
       is that verdict.
    3. A word-boundary tie word (``tie``, ``draw``, ``neither``, ``equal``,
       ``equally``, ``same``) is a tie — an explicit statement of one outranks
       the A/B mentions such a sentence necessarily contains.
    4. Otherwise collect the distinct verdicts named by a standalone capital
       ``A``/``B`` or a ``response``/``answer``/``option`` label. Exactly one
       distinct verdict is the answer; none, or both, is unreadable.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

import re
from typing import ClassVar

from pirn_agents.exceptions.unreadable_judge_reply_error import UnreadableJudgeReplyError


class PairwiseChoiceParser:
    """Read which presented response a judge reply picks: ``a``/``b``/``tie``, or raise."""

    #: Words that state a tie, on word boundaries — never as substrings.
    _tie: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(?:tie|tied|draw|neither|equal|equally|same)\b", re.IGNORECASE
    )
    #: An explicitly labelled choice: ``Response A``, ``answer_b``, ``option B``.
    _labelled: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(?:response|answer|option)[\s_-]*([ab])\b", re.IGNORECASE
    )
    #: A standalone capital ``A``/``B``. Capital deliberately: a lowercase
    #: ``\ba\b`` is the English article, which is how ``"B is a better answer"``
    #: used to be read as a vote for A.
    _bare: ClassVar[re.Pattern[str]] = re.compile(r"\b([AB])\b")

    #: Named in every ``UnreadableJudgeReplyError`` this parser raises.
    _expected: ClassVar[str] = "'A', 'B' or 'tie'"

    def parse(self, text: str) -> str:
        """Return the verdict ``text`` states.

        Args:
            text: The judge's reply text.

        Returns:
            One of ``"a"``, ``"b"``, or ``"tie"``.

        Raises:
            TypeError: If ``text`` is not a ``str``.
            UnreadableJudgeReplyError: If the reply names no verdict, or names
                both A and B without stating a tie. Never a fabricated
                ``"tie"``.
        """
        if not isinstance(text, str):
            raise TypeError(f"PairwiseChoiceParser: text must be a str, got {type(text).__name__}")
        stripped = text.strip()
        if not stripped:
            raise UnreadableJudgeReplyError(text, expected=type(self)._expected)
        bare = stripped.strip(".,!:;\"'()").lower()
        if bare in {"a", "b"}:
            return bare
        if type(self)._tie.search(stripped):
            return "tie"
        choices = {match.group(1).lower() for match in type(self)._labelled.finditer(stripped)}
        choices |= {match.group(1).lower() for match in type(self)._bare.finditer(stripped)}
        if len(choices) == 1:
            return choices.pop()
        raise UnreadableJudgeReplyError(text, expected=type(self)._expected)
