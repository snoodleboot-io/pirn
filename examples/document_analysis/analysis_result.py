"""``AnalysisResult`` — every analyser output for one document, plus its summary.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass

from examples.document_analysis.document import Document
from examples.document_analysis.keywords import Keywords
from examples.document_analysis.readability_score import ReadabilityScore
from examples.document_analysis.sentiment_score import SentimentScore
from examples.document_analysis.topic import Topic


@dataclass
class AnalysisResult:
    document: Document
    sentiment: SentimentScore
    readability: ReadabilityScore
    keywords: Keywords
    topic: Topic

    def summary(self) -> str:
        kw = ", ".join(w for w, _ in self.keywords.terms[:5])
        return (
            f"[{self.topic.label}] {self.document.title}\n"
            f"  Sentiment : {self.sentiment.label} ({self.sentiment.score:+.2f})\n"
            f"  Readability: grade {self.readability.grade_level:.1f}, "
            f"ease {self.readability.ease:.0f}/100\n"
            f"  Keywords  : {kw}\n"
            f"  Topic     : {self.topic.label} "
            f"(confidence {self.topic.confidence:.0%}, "
            f"signals: {', '.join(self.topic.matched_signals[:3])})"
        )
