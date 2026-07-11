"""Reciprocal Rank Fusion of several ranked id lists.

RRF merges rankings from heterogeneous retrievers (e.g. dense vs. lexical)
without needing comparable score scales: it uses only each item's *rank* in each
list. An item's fused score is the sum over lists of ``1 / (k + rank)`` (rank is
0-based here), and items are returned in descending fused-score order.

Math:
    .. math::

        \\text{RRF}(d) = \\sum_{r \\in R} \\frac{1}{k + \\text{rank}_r(d)}

References:
    - Cormack, Clarke & Buettcher, "Reciprocal Rank Fusion outperforms Condorcet
      and individual rank learning methods" (SIGIR 2009).
"""

from __future__ import annotations

from collections.abc import Sequence


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], *, k: int = 60
) -> list[tuple[str, float]]:
    """Fuse several ranked id lists into one via Reciprocal Rank Fusion.

    Args:
        rankings: Each inner sequence is an ordered list of ids (most relevant
            first) from one retriever.
        k: The RRF damping constant; larger ``k`` flattens the contribution of
            top ranks. Must be a positive integer.

    Returns:
        ``(id, fused_score)`` pairs ordered by descending fused score. Ties break
        by first appearance across the input rankings, giving a stable order.

    Raises:
        ValueError: If ``k`` is not a positive integer.
    """
    if not isinstance(k, int) or k <= 0:
        raise ValueError(f"k must be a positive int, got {k!r}")
    fused: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    order = 0
    for ranking in rankings:
        for rank, identifier in enumerate(ranking):
            fused[identifier] = fused.get(identifier, 0.0) + 1.0 / (k + rank)
            if identifier not in first_seen:
                first_seen[identifier] = order
                order += 1
    return sorted(fused.items(), key=lambda pair: (-pair[1], first_seen[pair[0]]))
