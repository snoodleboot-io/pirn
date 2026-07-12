"""``AutoMergingRetriever`` — merge retrieved leaves up to their parent.

The retrieval half of auto-merging. It retrieves leaf chunks, groups them by
parent, and — when the fraction of a parent's leaves that were retrieved meets
``merge_threshold`` — replaces those leaves with the single parent document.
Parents with only a stray leaf keep the precise leaf instead.

Algorithm:
    1. Validate ``query`` (str), ``store`` (:class:`VectorMemoryStore`),
       ``embedder`` (:class:`EmbeddingProvider`), ``top_k`` (positive int), and
       ``merge_threshold`` (0 < t <= 1).
    2. Embed the query and over-fetch leaf matches.
    3. Group matches by ``parent_id`` (best child score first).
    4. Merge a group to its parent when
       ``retrieved_leaves / sibling_count >= merge_threshold``; otherwise keep
       the individual leaves.
    5. Return up to ``top_k`` results ordered by score.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.embedding_provider import EmbeddingProvider

from pirn_agents.vector_stores.vector_match import VectorMatch
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore


class AutoMergingRetriever(Knot):
    """Retrieve leaves and merge them up to their parent past a threshold."""

    def __init__(
        self,
        *,
        query: Knot | str,
        store: Knot | VectorMemoryStore,
        embedder: Knot | EmbeddingProvider,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        candidate_multiplier: Knot | int = 4,
        merge_threshold: Knot | float = 0.5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            store=store,
            embedder=embedder,
            top_k=top_k,
            candidate_multiplier=candidate_multiplier,
            merge_threshold=merge_threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        store: VectorMemoryStore,
        embedder: EmbeddingProvider,
        top_k: int = 5,
        candidate_multiplier: int = 4,
        merge_threshold: float = 0.5,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Retrieve leaves and merge to parents past ``merge_threshold``.

        Args:
            query: The user query.
            store: The vector store holding leaf records.
            embedder: The provider embedding the query.
            top_k: Maximum number of results to return.
            candidate_multiplier: Over-fetch factor for leaf matches.
            merge_threshold: Fraction of a parent's leaves that triggers a merge.

        Returns:
            Up to ``top_k`` result mappings, each a merged parent or a precise leaf.

        Raises:
            TypeError: If ``query``/``store``/``embedder`` are the wrong type.
            ValueError: If ``top_k``/``candidate_multiplier`` are not positive ints
                or ``merge_threshold`` is outside ``(0, 1]``.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"AutoMergingRetriever: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(store, VectorMemoryStore):
            raise TypeError(
                f"AutoMergingRetriever: store must be a VectorMemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"AutoMergingRetriever: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"AutoMergingRetriever: top_k must be a positive int, got {top_k!r}")
        if not isinstance(candidate_multiplier, int) or candidate_multiplier <= 0:
            raise ValueError(
                "AutoMergingRetriever: candidate_multiplier must be a positive int, "
                f"got {candidate_multiplier!r}"
            )
        if not isinstance(merge_threshold, (int, float)) or not 0.0 < float(merge_threshold) <= 1.0:
            raise ValueError(
                f"AutoMergingRetriever: merge_threshold must be in (0, 1], got {merge_threshold!r}"
            )
        vectors = await embedder.embed([query])
        matches = await store.query(vectors[0], top_k=top_k * candidate_multiplier)
        groups: dict[str, list[VectorMatch]] = {}
        order: list[str] = []
        for match in matches:
            parent_id = match.metadata.get("parent_id")
            if not isinstance(parent_id, str):
                continue
            if parent_id not in groups:
                groups[parent_id] = []
                order.append(parent_id)
            groups[parent_id].append(match)
        results: list[Mapping[str, Any]] = []
        for parent_id in order:
            members = groups[parent_id]
            best = members[0]
            sibling_count = best.metadata.get("sibling_count")
            sibling_count = sibling_count if isinstance(sibling_count, int) and sibling_count else 1
            if len(members) / sibling_count >= float(merge_threshold):
                parent_text = best.metadata.get("parent_text")
                results.append(
                    {
                        "id": parent_id,
                        "text": parent_text if isinstance(parent_text, str) else "",
                        "score": best.score,
                        "merged": True,
                    }
                )
            else:
                for member in members:
                    results.append(
                        {
                            "id": member.id,
                            "text": member.document if member.document is not None else "",
                            "score": member.score,
                            "merged": False,
                        }
                    )
        results.sort(key=lambda doc: float(doc["score"]), reverse=True)
        return results[:top_k]
