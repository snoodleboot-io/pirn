"""``SemanticMatch`` — embedding cosine-similarity match with a threshold."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from pirn_agents.evaluation.cosine_similarity import CosineSimilarity
from pirn_agents.evaluation.metric import Metric
from pirn_agents.evaluation.metric_result import MetricResult


class SemanticMatch(Metric):
    """Score the cosine similarity of prediction and reference embeddings.

    Backend-free by injection: the caller supplies ``embedder``, a pure function
    mapping a string to a vector, so this metric depends on *no* specific
    embedding backend (a stub embedder is used in tests; a real provider wraps
    its own model). The reported ``score`` is the raw cosine similarity clamped
    to ``[0.0, 1.0]``; ``detail["passed"]`` records whether it met ``threshold``.
    """

    def __init__(
        self,
        *,
        embedder: Callable[[str], Sequence[float]],
        threshold: float = 0.8,
    ) -> None:
        """Configure the embedder and pass threshold.

        Args:
            embedder: Pure function returning an embedding vector for a string.
                Both strings must map to equal-length vectors.
            threshold: Similarity at or above which the match is considered a
                pass.

        Raises:
            TypeError: If ``embedder`` is not callable or ``threshold`` is not a
                real number.
        """
        if not callable(embedder):
            raise TypeError(
                f"SemanticMatch: embedder must be callable, got {type(embedder).__name__}"
            )
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise TypeError(
                f"SemanticMatch: threshold must be a real number, got {type(threshold).__name__}"
            )
        self._embedder = embedder
        self._threshold = threshold
        self._cosine = CosineSimilarity()

    @property
    def name(self) -> str:
        """The metric's stable identifier."""
        return "semantic_match"

    def score(self, actual: Any, expected: Any = None) -> MetricResult:
        """Score ``actual`` (the prediction) against ``expected`` (the reference).

        Args:
            actual: The produced output string.
            expected: The gold reference string.

        Returns:
            A :class:`MetricResult` named ``"semantic_match"``.

        Raises:
            TypeError: If either string argument is not a ``str``.
        """
        if not isinstance(actual, str):
            raise TypeError(
                f"SemanticMatch: prediction must be a str, got {type(actual).__name__}"
            )
        if not isinstance(expected, str):
            raise TypeError(
                f"SemanticMatch: reference must be a str, got {type(expected).__name__}"
            )
        similarity = self._cosine.compute(self._embedder(actual), self._embedder(expected))
        clamped = max(0.0, min(1.0, similarity))
        return MetricResult(
            name="semantic_match",
            score=clamped,
            detail={
                "similarity": similarity,
                "threshold": float(self._threshold),
                "passed": similarity >= self._threshold,
            },
        )
