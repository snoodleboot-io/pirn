"""Document analysis pipeline using class-based knots.

Demonstrates subclassing ``Knot`` directly to build typed, reusable analysis
components — including a shared base class with helper methods, config injected
as constructor kwargs, and parallel branches that feed a single report knot.

Pipeline shape:

    DocumentLoader ──► TextNormaliser ──┬──► SentimentScorer  ──┐
                                        ├──► ReadabilityScorer   ├──► AnalysisReport
                                        ├──► KeywordExtractor    │
                                        └──► TopicClassifier   ──┘

Run with:
    uv run python -m examples.document_analysis
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from examples.document_analysis.analysis_report import AnalysisReport
from examples.document_analysis.analysis_result import AnalysisResult
from examples.document_analysis.document_loader import DocumentLoader
from examples.document_analysis.keyword_extractor import KeywordExtractor
from examples.document_analysis.readability_scorer import ReadabilityScorer
from examples.document_analysis.sentiment_scorer import SentimentScorer
from examples.document_analysis.text_normaliser import TextNormaliser
from examples.document_analysis.topic_classifier import TopicClassifier


class DocumentAnalysis:
    """Builds and runs the class-based document analysis tapestry."""

    _articles: ClassVar[tuple[dict[str, str], ...]] = (
        {
            "title": "Breakthrough in Quantum Computing Promises Faster Drug Discovery",
            "body": (
                "Scientists at a leading research institute have achieved a remarkable "
                "breakthrough in quantum computing, successfully demonstrating a 1,000-qubit "
                "processor that operates with unprecedented reliability. The innovation could "
                "accelerate drug discovery by simulating molecular interactions at a scale "
                "previously impossible with classical hardware. Clinical trials for new "
                "treatments could benefit enormously from the improved computational power, "
                "reducing the time from hypothesis to viable therapy. The algorithm developed "
                "by the team is considered a brilliant advance in both physics and biology, "
                "with positive implications for vaccine research and gene therapy. Several "
                "technology companies have already expressed interest in licensing the "
                "platform."
            ),
            "source": "ScienceDaily",
        },
        {
            "title": "Central Bank Raises Interest Rates Amid Inflation Concerns",
            "body": (
                "The central bank announced a further increase in the benchmark interest rate "
                "following persistent inflation that has eroded consumer purchasing power. "
                "Financial analysts warn the decision could slow GDP growth and reduce equity "
                "market returns in the short term. Bank stocks fell sharply as investors "
                "reassessed portfolio risk, with several high-growth assets showing significant "
                "loss. The policy rate adjustment, while painful for borrowers, is expected to "
                "stabilise the economy over the medium term. Government officials acknowledged "
                "the difficult trade-off between controlling inflation and sustaining economic "
                "growth. Capital markets have already priced in further rate increases, though "
                "some analysts consider the current pace excessive and potentially dangerous."
            ),
            "source": "FinancialTimes",
        },
        {
            "title": "New Study Links Ultra-Processed Food to Mental Health Decline",
            "body": (
                "A large-scale clinical study tracking 50,000 patients over a decade has found "
                "a strong correlation between consumption of ultra-processed food and increased "
                "risk of depression and anxiety. Researchers analysed nutritional data alongside "
                "mental health assessments, finding that poor diet was associated with a 23% "
                "higher incidence of serious mental health symptoms. The findings reinforce calls "
                "for stricter food labelling regulations and investment in preventive healthcare. "
                "Medical professionals emphasise that treatment should address diet as a primary "
                "factor, not merely prescribe medication. The study, published in a leading "
                "journal, has already influenced policy discussions around nutrition standards "
                "in hospitals and schools. Wellness advocates hailed the research as a positive "
                "step toward holistic patient care."
            ),
            "source": "HealthWeekly",
        },
    )

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire loader → normaliser → four parallel analysers → report."""
        with Tapestry(history=history) as t:
            title = Parameter("title", str, _config=KnotConfig(id="title"))
            body = Parameter("body", str, _config=KnotConfig(id="body"))
            source = Parameter("source", str, _config=KnotConfig(id="source"))
            loader = DocumentLoader(
                title=title,
                body=body,
                source=source,
                _config=KnotConfig(id="loader"),
            )
            normalised = TextNormaliser(
                document=loader,
                _config=KnotConfig(id="normalised"),
            )
            sentiment = SentimentScorer(
                text=normalised,
                _config=KnotConfig(id="sentiment"),
            )
            readability = ReadabilityScorer(
                text=normalised,
                _config=KnotConfig(id="readability"),
            )
            keywords = KeywordExtractor(
                text=normalised,
                max_keywords=10,
                _config=KnotConfig(id="keywords"),
            )
            topic = TopicClassifier(
                text=normalised,
                _config=KnotConfig(id="topic"),
            )
            AnalysisReport(
                document=loader,
                sentiment=sentiment,
                readability=readability,
                keywords=keywords,
                topic=topic,
                _config=KnotConfig(id="report"),
            )
        return t

    @classmethod
    async def main(cls) -> None:
        """Analyse every sample article and print its summary."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[1] / "pirn.db"))
        t = cls.build_tapestry(history=history)

        print("\n── Document Analysis Pipeline ──\n")

        for article in cls._articles:
            r = await t.run(RunRequest(parameters=dict(article)))
            if not r.succeeded:
                exc = r.exceptions[0]
                print(f"  FAILED ({exc.knot_id}): {exc.message[:80]}")
                continue
            result: AnalysisResult = r.outputs["report"]
            print(result.summary())
            print()

        history.close()
