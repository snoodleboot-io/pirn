"""``ParentDocumentRetriever`` — match children, return their parents.

The retrieval half of small-to-big. It embeds the query, matches precise child
records, and returns each matched child's *parent* text (deduplicated so a parent
appears once), giving the synthesizer the fuller context around the precise hit.

Algorithm:
    1. Validate ``query`` (str), ``store`` (:class:`VectorMemoryStore`),
       ``embedder`` (:class:`EmbeddingProvider`), and ``top_k`` (positive int).
    2. Embed the query and over-fetch child matches.
    3. Walk matches in rank order, emitting each parent once, until ``top_k``
       distinct parents are collected.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.embedding_provider import EmbeddingProvider

from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore


class ParentDocumentRetriever(Knot):
    """Retrieve precise children and return their deduplicated parent documents."""

    def __init__(
        self,
        *,
        query: Knot | str,
        store: Knot | VectorMemoryStore,
        embedder: Knot | EmbeddingProvider,
        _config: KnotConfig,
        top_k: Knot | int = 3,
        candidate_multiplier: Knot | int = 4,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            store=store,
            embedder=embedder,
            top_k=top_k,
            candidate_multiplier=candidate_multiplier,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        store: VectorMemoryStore,
        embedder: EmbeddingProvider,
        top_k: int = 3,
        candidate_multiplier: int = 4,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Return up to ``top_k`` distinct parent documents for the query.

        Args:
            query: The user query.
            store: The vector store holding child records.
            embedder: The provider embedding the query.
            top_k: Number of distinct parents to return.
            candidate_multiplier: Over-fetch factor for child matches.

        Returns:
            Parent documents as ``{"id", "text", "score"}`` mappings, in rank order.

        Raises:
            TypeError: If ``query``/``store``/``embedder`` are the wrong type.
            ValueError: If ``top_k``/``candidate_multiplier`` are not positive ints.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"ParentDocumentRetriever: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(store, VectorMemoryStore):
            raise TypeError(
                f"ParentDocumentRetriever: store must be a VectorMemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"ParentDocumentRetriever: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                f"ParentDocumentRetriever: top_k must be a positive int, got {top_k!r}"
            )
        if not isinstance(candidate_multiplier, int) or candidate_multiplier <= 0:
            raise ValueError(
                "ParentDocumentRetriever: candidate_multiplier must be a positive int, "
                f"got {candidate_multiplier!r}"
            )
        vectors = await embedder.embed([query])
        matches = await store.query(vectors[0], top_k=top_k * candidate_multiplier)
        parents: dict[str, Mapping[str, Any]] = {}
        for match in matches:
            parent_id = match.metadata.get("parent_id")
            parent_text = match.metadata.get("parent_text")
            if not isinstance(parent_id, str) or not isinstance(parent_text, str):
                continue
            if parent_id not in parents:
                parents[parent_id] = {
                    "id": parent_id,
                    "text": parent_text,
                    "score": match.score,
                }
            if len(parents) >= top_k:
                break
        return list(parents.values())
