"""``KeywordExtractor`` — TF-IDF-style keyword extraction knot.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from typing import Any

from examples.document_analysis.base_analyser import _BaseAnalyser
from examples.document_analysis.keywords import Keywords
from examples.document_analysis.normalised_text import NormalisedText


class KeywordExtractor(_BaseAnalyser):
    """TF-IDF-style keyword extraction.

    ``max_keywords`` is injected as a plain config value at construction
    time — no Knot parent needed, just pass an int.
    """

    async def process(
        self,
        text: NormalisedText,
        max_keywords: int,
        **_: Any,
    ) -> Keywords:
        return Keywords(terms=self._tfidf(text.words, top=max_keywords))
