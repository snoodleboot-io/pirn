"""``SentimentScorer`` — lexicon-based sentiment scoring knot.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from typing import Any, ClassVar

from examples.document_analysis.base_analyser import _BaseAnalyser
from examples.document_analysis.normalised_text import NormalisedText
from examples.document_analysis.sentiment_score import SentimentScore


class SentimentScorer(_BaseAnalyser):
    """Lexicon-based sentiment scoring.

    Counts positive and negative signal words and returns a normalised
    score in [-1, +1].  No constructor config needed — the lexicon is
    class-level state shared across all instances.
    """

    _pos: ClassVar[frozenset[str]] = frozenset(
        "good great excellent amazing wonderful fantastic brilliant "
        "outstanding superb positive success successful achieve "
        "improve improvement growth advance promising benefit "
        "innovative efficient effective powerful robust reliable".split()
    )
    _neg: ClassVar[frozenset[str]] = frozenset(
        "bad poor terrible awful horrible dreadful failure fail "
        "negative decline decrease loss problem issue risk danger "
        "concern threat weakness flaw error bug crash slow expensive".split()
    )

    async def process(self, text: NormalisedText, **_: Any) -> SentimentScore:
        pos = sum(1 for w in text.words if w in self._pos)
        neg = sum(1 for w in text.words if w in self._neg)
        total = pos + neg or 1
        raw = (pos - neg) / total
        if raw > 0.15:
            label = "positive"
        elif raw < -0.15:
            label = "negative"
        else:
            label = "neutral"
        return SentimentScore(
            label=label, score=round(raw, 3), positive_hits=pos, negative_hits=neg
        )
