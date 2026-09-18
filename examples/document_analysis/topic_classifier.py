"""``TopicClassifier`` — rule-based topic classifier knot.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from typing import Any, ClassVar

from examples.document_analysis.base_analyser import _BaseAnalyser
from examples.document_analysis.normalised_text import NormalisedText
from examples.document_analysis.topic import Topic


class TopicClassifier(_BaseAnalyser):
    """Rule-based topic classifier using signal-word dictionaries.

    Each topic has a set of signal words.  The topic whose signals appear
    most frequently in the document wins; confidence is the fraction of
    signals matched vs. total signal hits across all topics.
    """

    _topics: ClassVar[dict[str, frozenset[str]]] = {
        "technology": frozenset(
            "software hardware algorithm data model neural network ai machine "
            "learning cloud computing platform api code programming developer "
            "digital tech innovation startup".split()
        ),
        "finance": frozenset(
            "market stock price revenue profit loss investment fund portfolio "
            "bank financial economy growth gdp inflation rate capital equity "
            "dividend asset liability".split()
        ),
        "science": frozenset(
            "research study experiment hypothesis result finding evidence "
            "analysis clinical trial vaccine gene protein cell biology "
            "physics chemistry quantum particle".split()
        ),
        "health": frozenset(
            "health patient medical treatment therapy disease symptom doctor "
            "hospital drug prescription nutrition fitness diet wellness "
            "mental care prevention".split()
        ),
        "politics": frozenset(
            "government policy election vote parliament senator president law "
            "regulation bill legislation democrat republican policy reform "
            "administration official minister".split()
        ),
    }

    async def process(self, text: NormalisedText, **_: Any) -> Topic:
        counts: dict[str, list[str]] = {t: [] for t in self._topics}
        for word in text.words:
            for topic, signals in self._topics.items():
                if word in signals:
                    counts[topic].append(word)

        total_hits = sum(len(v) for v in counts.values()) or 1
        best = max(counts, key=lambda t: len(counts[t]))
        best_hits = len(counts[best])

        return Topic(
            label=best,
            confidence=round(best_hits / total_hits, 3),
            matched_signals=list(dict.fromkeys(counts[best]))[:10],
        )
