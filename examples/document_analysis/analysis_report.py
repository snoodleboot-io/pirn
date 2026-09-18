"""``AnalysisReport`` — assembles all analysis outputs into one ``AnalysisResult``.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.document_analysis.analysis_result import AnalysisResult
from examples.document_analysis.document import Document
from examples.document_analysis.keywords import Keywords
from examples.document_analysis.readability_score import ReadabilityScore
from examples.document_analysis.sentiment_score import SentimentScore
from examples.document_analysis.topic import Topic


class AnalysisReport(Knot):
    """Assembles all analysis outputs into a single ``AnalysisResult``.

    All five inputs arrive as resolved values — four from the parallel
    analysis branches, one from the shared normalised text source.
    """

    async def process(
        self,
        document: Document,
        sentiment: SentimentScore,
        readability: ReadabilityScore,
        keywords: Keywords,
        topic: Topic,
        **_: Any,
    ) -> AnalysisResult:
        return AnalysisResult(
            document=document,
            sentiment=sentiment,
            readability=readability,
            keywords=keywords,
            topic=topic,
        )
