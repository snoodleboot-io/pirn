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
    uv run python examples/document_analysis/document_analysis.py
"""

from __future__ import annotations

import asyncio
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- data models


@dataclass
class Document:
    title: str
    body: str
    source: str


@dataclass
class NormalisedText:
    title: str
    body: str
    words: list[str]
    sentences: list[str]
    word_count: int
    sentence_count: int


@dataclass
class SentimentScore:
    label: str  # "positive" | "neutral" | "negative"
    score: float  # -1.0 … +1.0
    positive_hits: int
    negative_hits: int


@dataclass
class ReadabilityScore:
    grade_level: float  # US grade level approximation
    ease: float  # Flesch reading-ease 0-100
    avg_sentence_length: float
    avg_word_length: float


@dataclass
class Keywords:
    terms: list[tuple[str, float]]  # (word, tf-idf-ish score), descending


@dataclass
class Topic:
    label: str
    confidence: float
    matched_signals: list[str]


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


# ----------------------------------------------------------------- knots


class DocumentLoader(Knot):
    """Validates and packages raw article fields into a ``Document``.

    Trims whitespace and enforces non-empty title + body.
    """

    async def process(self, title: str, body: str, source: str, **_: Any) -> Document:
        title = title.strip()
        body = body.strip()
        if not title:
            raise ValueError("Document title must not be empty")
        if not body:
            raise ValueError("Document body must not be empty")
        return Document(title=title, body=body, source=source)


class TextNormaliser(Knot):
    """Cleans a document and pre-computes tokens for downstream analysers.

    Strips HTML tags, collapses whitespace, lower-cases for token lists,
    and splits into sentences and words.  The original case is preserved
    in ``body`` for display; ``words`` is the lower-cased token list.
    """

    _HTML_TAG = re.compile(r"<[^>]+>")
    _PUNCT = re.compile(r"[^a-z0-9\s]")
    _SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

    async def process(self, document: Document, **_: Any) -> NormalisedText:
        clean = self._HTML_TAG.sub(" ", document.body)
        clean = re.sub(r"\s+", " ", clean).strip()

        sentences = [s.strip() for s in self._SENT_SPLIT.split(clean) if s.strip()]
        words = self._PUNCT.sub("", clean.lower()).split()

        return NormalisedText(
            title=document.title,
            body=clean,
            words=words,
            sentences=sentences,
            word_count=len(words),
            sentence_count=max(len(sentences), 1),
        )


class _BaseAnalyser(Knot):
    """Shared helpers for text analysis knots.

    Subclasses receive a ``NormalisedText`` and use ``_freq``, ``_tfidf``,
    and ``_avg_word_len`` rather than re-implementing tokenisation.
    """

    # Common English stop words to exclude from keyword / signal matching.
    _STOP = frozenset(
        "a an the and or but in on at to for of with is are was were be been "
        "being have has had do does did will would could should may might "
        "this that these those it its i we you he she they my our your".split()
    )

    def _freq(self, words: list[str]) -> Counter:
        return Counter(w for w in words if w not in self._STOP and len(w) > 2)

    def _tfidf(self, words: list[str], top: int) -> list[tuple[str, float]]:
        freq = self._freq(words)
        total = sum(freq.values()) or 1
        # Simplified TF score; no IDF corpus — penalise very common short words.
        scored = {w: (c / total) * math.log(1 + len(w)) for w, c in freq.items()}
        return sorted(scored.items(), key=lambda x: x[1], reverse=True)[:top]

    def _avg_word_len(self, words: list[str]) -> float:
        return sum(len(w) for w in words) / max(len(words), 1)


class SentimentScorer(_BaseAnalyser):
    """Lexicon-based sentiment scoring.

    Counts positive and negative signal words and returns a normalised
    score in [-1, +1].  No constructor config needed — the lexicon is
    class-level state shared across all instances.
    """

    _POS = frozenset(
        "good great excellent amazing wonderful fantastic brilliant "
        "outstanding superb positive success successful achieve "
        "improve improvement growth advance promising benefit "
        "innovative efficient effective powerful robust reliable".split()
    )
    _NEG = frozenset(
        "bad poor terrible awful horrible dreadful failure fail "
        "negative decline decrease loss problem issue risk danger "
        "concern threat weakness flaw error bug crash slow expensive".split()
    )

    async def process(self, text: NormalisedText, **_: Any) -> SentimentScore:
        pos = sum(1 for w in text.words if w in self._POS)
        neg = sum(1 for w in text.words if w in self._NEG)
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


class ReadabilityScorer(_BaseAnalyser):
    """Flesch reading-ease approximation.

    Uses average sentence length and average syllable count (estimated
    from vowel runs) to produce a 0-100 ease score and a US grade level.
    """

    _VOWELS = re.compile(r"[aeiou]+")

    def _syllables(self, word: str) -> int:
        return max(len(self._VOWELS.findall(word)), 1)

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


class TopicClassifier(_BaseAnalyser):
    """Rule-based topic classifier using signal-word dictionaries.

    Each topic has a set of signal words.  The topic whose signals appear
    most frequently in the document wins; confidence is the fraction of
    signals matched vs. total signal hits across all topics.
    """

    _TOPICS: ClassVar[dict[str, frozenset[str]]] = {
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
        counts: dict[str, list[str]] = {t: [] for t in self._TOPICS}
        for word in text.words:
            for topic, signals in self._TOPICS.items():
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


# ----------------------------------------------------------------- tapestry


def build_tapestry(history=None) -> Tapestry:
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


# ----------------------------------------------------------------- sample articles


ARTICLES = [
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
            "technology companies have already expressed interest in licensing the platform."
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
]


# ----------------------------------------------------------------- main


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    print("\n── Document Analysis Pipeline ──\n")

    for article in ARTICLES:
        r = await t.run(RunRequest(parameters=article))
        if not r.succeeded:
            exc = r.exceptions[0]
            print(f"  FAILED ({exc.knot_id}): {exc.message[:80]}")
            continue
        result: AnalysisResult = r.outputs["report"]
        print(result.summary())
        print()

    history.close()


if __name__ == "__main__":
    asyncio.run(main())
