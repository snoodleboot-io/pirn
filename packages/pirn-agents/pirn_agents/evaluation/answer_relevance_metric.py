"""``AnswerRelevanceMetric`` — embedding similarity of answer to its question."""

from __future__ import annotations

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.evaluation.cosine_similarity import CosineSimilarity
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.rag_sample import RagSample


class AnswerRelevanceMetric:
    """RAGAS-style answer relevance: does the answer address the question?

    Formula
    -------
    The query and the answer are embedded with a pluggable
    :class:`pirn_agents.embedding_provider.EmbeddingProvider` and scored
    by cosine similarity (clamped to ``[0.0, 1.0]``)::

        answer_relevance = clamp01( cos( embed(query), embed(answer) ) )

    A focused, on-topic answer scores high; an evasive or off-topic answer
    scores low. The embedding backend is injected, so the metric privileges no
    vendor and stays backend-free at import time (a stub provider is used in
    tests).
    """

    def __init__(self, *, embedder: EmbeddingProvider) -> None:
        """Store the embedding provider used to embed query and answer.

        Raises:
            TypeError: If ``embedder`` is not an :class:`EmbeddingProvider`.
        """
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"AnswerRelevanceMetric: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        self._embedder = embedder
        self._cosine = CosineSimilarity()

    async def evaluate(self, sample: RagSample) -> MetricResult:
        """Score how relevant ``sample.answer`` is to ``sample.query``.

        Raises:
            TypeError: If ``sample`` is not a :class:`RagSample`.
        """
        if not isinstance(sample, RagSample):
            raise TypeError(
                f"AnswerRelevanceMetric.evaluate: sample must be a RagSample, "
                f"got {type(sample).__name__}"
            )
        vectors = await self._embedder.embed([sample.query, sample.answer])
        similarity = self._cosine.compute(vectors[0], vectors[1])
        clamped = max(0.0, min(1.0, similarity))
        return MetricResult(
            name="answer_relevance",
            score=clamped,
            detail={"similarity": similarity},
        )
