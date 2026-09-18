"""``FuseVariantHits`` — ``Aggregator`` combine target fusing per-variant rankings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.retrieval.reciprocal_rank_fusion import ReciprocalRankFusion


class FuseVariantHits:
    """``Aggregator`` combine target: fuse per-variant rankings with RRF."""

    @staticmethod
    def aggregate(
        count: int, rrf_k: int, top_k: int, **searches: list[Mapping[str, Any]]
    ) -> list[Mapping[str, Any]]:
        """Fuse the fan-out's per-variant searches in query order.

        Args:
            count: How many ``search_{i}`` parents the aggregator has.
            rrf_k: The RRF damping constant.
            top_k: Maximum number of fused documents to return.
            **searches: Each ``VariantSearch``'s ranked hits, keyed ``search_{i}``.

        Returns:
            Up to ``top_k`` fused documents, each with a ``fusion_score``.
        """
        return FuseVariantHits.combine(
            [searches[f"search_{index}"] for index in range(count)],
            rrf_k=rrf_k,
            top_k=top_k,
        )

    @staticmethod
    def combine(
        items: list[list[Mapping[str, Any]]], *, rrf_k: int, top_k: int
    ) -> list[Mapping[str, Any]]:
        """Fuse per-variant ranked hit lists into the top ``top_k`` documents.

        Args:
            items: One ranked hit list per query variant.
            rrf_k: The RRF damping constant.
            top_k: Maximum number of fused documents to return.

        Returns:
            Up to ``top_k`` document mappings ordered by fused score, each
            with a ``fusion_score`` key.
        """
        representative: dict[str, Mapping[str, Any]] = {}
        rankings: list[list[str]] = []
        for hits in items:
            ranking: list[str] = []
            for hit in hits:
                key = FuseVariantHits._doc_key(hit)
                representative.setdefault(key, hit)
                ranking.append(key)
            rankings.append(ranking)
        fused = ReciprocalRankFusion.fuse(rankings, k=rrf_k)
        results: list[Mapping[str, Any]] = []
        for key, score in fused[:top_k]:
            merged = dict(representative[key])
            merged["fusion_score"] = score
            results.append(merged)
        return results

    @staticmethod
    def _doc_key(hit: Mapping[str, Any]) -> str:
        """Return a stable identity key for a retrieved hit."""
        identifier = hit.get("id")
        if identifier is not None:
            return str(identifier)
        return repr(sorted((str(k), str(v)) for k, v in hit.items()))
