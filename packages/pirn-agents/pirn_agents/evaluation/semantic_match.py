"""``semantic_match`` — embedding cosine-similarity match with a threshold."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from pirn_agents.evaluation.cosine_similarity import cosine_similarity
from pirn_agents.evaluation.metric_result import MetricResult


def semantic_match(
    prediction: str,
    reference: str,
    *,
    embedder: Callable[[str], Sequence[float]],
    threshold: float = 0.8,
) -> MetricResult:
    """Score the cosine similarity of ``prediction`` and ``reference`` embeddings.

    Backend-free by injection: the caller supplies ``embedder``, a pure function
    mapping a string to a vector, so this metric depends on *no* specific
    embedding backend (a stub embedder is used in tests; a real provider wraps
    its own model). The reported ``score`` is the raw cosine similarity clamped
    to ``[0.0, 1.0]``; ``detail["passed"]`` records whether it met ``threshold``.

    Args:
        prediction: The produced output string.
        reference: The gold reference string.
        embedder: Pure function returning an embedding vector for a string. Both
            strings must map to equal-length vectors.
        threshold: Similarity at or above which the match is considered a pass.

    Returns:
        A :class:`MetricResult` named ``"semantic_match"``.

    Raises:
        TypeError: If either string argument is not a ``str``, ``embedder`` is
            not callable, or ``threshold`` is not a real number.
    """
    if not isinstance(prediction, str):
        raise TypeError(
            f"semantic_match: prediction must be a str, got {type(prediction).__name__}"
        )
    if not isinstance(reference, str):
        raise TypeError(f"semantic_match: reference must be a str, got {type(reference).__name__}")
    if not callable(embedder):
        raise TypeError(f"semantic_match: embedder must be callable, got {type(embedder).__name__}")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise TypeError(
            f"semantic_match: threshold must be a real number, got {type(threshold).__name__}"
        )
    similarity = cosine_similarity(embedder(prediction), embedder(reference))
    clamped = max(0.0, min(1.0, similarity))
    return MetricResult(
        name="semantic_match",
        score=clamped,
        detail={
            "similarity": similarity,
            "threshold": float(threshold),
            "passed": similarity >= threshold,
        },
    )
