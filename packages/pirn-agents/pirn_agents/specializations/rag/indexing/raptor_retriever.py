"""``RaptorRetriever`` — collapsed-tree retrieval over a RAPTOR index.

RAPTOR supports "collapsed tree" retrieval: rather than descending the tree, all
nodes across every level (leaf chunks *and* summaries) are treated as one flat
pool and the query matches whichever nodes — detailed or abstractive — are most
relevant. Summary nodes let a broad question hit a high-level node while a
specific question still hits a precise leaf.

Algorithm:
    1. Validate ``query`` (str), ``store`` (:class:`VectorMemoryStore`),
       ``embedder`` (:class:`EmbeddingProvider`), and ``top_k`` (positive int).
    2. Embed the query and match ``top_k`` records filtered to RAPTOR nodes
       (``kind == "raptor"``), so the ``:meta`` marker is excluded.
    3. Return each hit with its node text and level.

References:
    - Sarthi et al., "RAPTOR" (ICLR 2024): https://arxiv.org/abs/2401.18059
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore


class RaptorRetriever(Knot):
    """Match the query across all RAPTOR nodes (collapsed-tree retrieval)."""

    def __init__(
        self,
        *,
        query: Knot | str,
        store: Knot | VectorMemoryStore,
        embedder: Knot | EmbeddingProvider,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            store=store,
            embedder=embedder,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        store: VectorMemoryStore,
        embedder: EmbeddingProvider,
        top_k: int = 5,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Return up to ``top_k`` best-matching RAPTOR nodes for the query.

        Args:
            query: The user query.
            store: The vector store holding the RAPTOR tree.
            embedder: The provider embedding the query.
            top_k: Number of nodes to return.

        Returns:
            Node mappings ``{"id", "text", "level", "score"}`` in rank order.

        Raises:
            TypeError: If ``query``/``store``/``embedder`` are the wrong type.
            ValueError: If ``top_k`` is not a positive integer.
        """
        if not isinstance(query, str):
            raise TypeError(f"RaptorRetriever: query must be a string, got {type(query).__name__}")
        if not isinstance(store, VectorMemoryStore):
            raise TypeError(
                f"RaptorRetriever: store must be a VectorMemoryStore, got {type(store).__name__}"
            )
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"RaptorRetriever: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"RaptorRetriever: top_k must be a positive int, got {top_k!r}")
        vectors = await embedder.embed([query])
        matches = await store.query(vectors[0], top_k=top_k, metadata_filter={"kind": "raptor"})
        return [
            {
                "id": match.id,
                "text": match.document or "",
                "level": match.metadata.get("level"),
                "score": match.score,
            }
            for match in matches
        ]
