"""``_BaseAnalyser`` — shared tokenisation helpers for the analysis knots.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import ClassVar

from pirn.core.knot import Knot


class _BaseAnalyser(Knot):
    """Shared helpers for text analysis knots.

    Subclasses receive a ``NormalisedText`` and use ``_freq``, ``_tfidf``,
    and ``_avg_word_len`` rather than re-implementing tokenisation.
    """

    # Common English stop words to exclude from keyword / signal matching.
    _stop: ClassVar[frozenset[str]] = frozenset(
        "a an the and or but in on at to for of with is are was were be been "
        "being have has had do does did will would could should may might "
        "this that these those it its i we you he she they my our your".split()
    )

    def _freq(self, words: list[str]) -> Counter[str]:
        return Counter(w for w in words if w not in self._stop and len(w) > 2)

    def _tfidf(self, words: list[str], top: int) -> list[tuple[str, float]]:
        freq = self._freq(words)
        total = sum(freq.values()) or 1
        # Simplified TF score; no IDF corpus — penalise very common short words.
        scored = {w: (c / total) * math.log(1 + len(w)) for w, c in freq.items()}
        return sorted(scored.items(), key=lambda x: x[1], reverse=True)[:top]

    def _avg_word_len(self, words: list[str]) -> float:
        return sum(len(w) for w in words) / max(len(words), 1)
