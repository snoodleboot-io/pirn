"""``ReadabilityScorer`` — Flesch reading-ease approximation knot.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from examples.document_analysis.base_analyser import _BaseAnalyser
from examples.document_analysis.normalised_text import NormalisedText
from examples.document_analysis.readability_score import ReadabilityScore


class ReadabilityScorer(_BaseAnalyser):
    """Flesch reading-ease approximation.

    Uses average sentence length and average syllable count (estimated
    from vowel runs) to produce a 0-100 ease score and a US grade level.
    """

    _vowels: ClassVar[re.Pattern[str]] = re.compile(r"[aeiou]+")

    def _syllables(self, word: str) -> int:
        return max(len(self._vowels.findall(word)), 1)

    async def process(self, text: NormalisedText, **_: Any) -> ReadabilityScore:
        asl = text.word_count / text.sentence_count
        asw = sum(self._syllables(w) for w in text.words) / max(text.word_count, 1)
        ease = max(0.0, min(100.0, 206.835 - 1.015 * asl - 84.6 * asw))
        grade = max(0.0, 0.39 * asl + 11.8 * asw - 15.59)
        return ReadabilityScore(
            grade_level=round(grade, 1),
            ease=round(ease, 1),
            avg_sentence_length=round(asl, 1),
            avg_word_length=round(self._avg_word_len(text.words), 2),
        )
