"""``HybridRetriever`` — concurrent dense + lexical retrieval fused with RRF.

A :class:`Knot` that retrieves from a dense
:class:`~pirn_agents.vector_stores.vector_memory_store.VectorMemoryStore` and a
lexical :class:`~pirn_agents.retrieval.bm25_index.Bm25Index` **concurrently**,
then fuses the two rankings with Reciprocal Rank Fusion. Dense retrieval is
async I/O and BM25 scoring is CPU-bound, so the CPU arm is offloaded to a thread
and both arms are awaited together with :func:`asyncio.gather` — the fusion is
done over whichever ranks come back.

Algorithm:
    1. Validate ``query``, ``store``, ``lexical``, ``embedder``, and ``top_k``.
    2. Concurrently: embed the query and run a dense ``store.query`` for the
       nearest ids; run ``lexical.search`` on a worker thread for the BM25 ids.
    3. Fuse the two ranked id lists with
       :func:`~pirn_agents.retrieval.reciprocal_rank_fusion.reciprocal_rank_fusion`.
    4. Return the top ``top_k`` fused hits as ``{"id", "score"}`` mappings.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.embedding_provider import EmbeddingProvider

from pirn_agents.retrieval.bm25_index import Bm25Index
from pirn_agents.retrieval.reciprocal_rank_fusion import reciprocal_rank_fusion
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore


class HybridRetriever(Knot):
    """Fuse dense and lexical retrieval concurrently via Reciprocal Rank Fusion."""

    def __init__(
        self,
        *,
        query: Knot | str,
        store: Knot | VectorMemoryStore,
        lexical: Knot | Any,
        embedder: Knot | EmbeddingProvider,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        candidate_multiplier: Knot | int = 4,
        rrf_k: Knot | int = 60,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            store=store,
            lexical=lexical,
            embedder=embedder,
            top_k=top_k,
            candidate_multiplier=candidate_multiplier,
            rrf_k=rrf_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        store: VectorMemoryStore,
        lexical: Any,
        embedder: EmbeddingProvider,
        top_k: int = 5,
        candidate_multiplier: int = 4,
        rrf_k: int = 60,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Retrieve dense + lexical candidates concurrently and fuse them via RRF.

        Args:
            query: The user query string.
            store: The dense vector store to query.
            lexical: The BM25 lexical index to search.
            embedder: The provider used to embed the query for dense retrieval.
            top_k: Number of fused hits to return.
            candidate_multiplier: Over-fetch factor per arm before fusion, so
                fusion sees more than ``top_k`` from each retriever.
            rrf_k: The RRF damping constant.

        Returns:
            Up to ``top_k`` ``{"id", "score"}`` mappings ordered by fused score.

        Raises:
            TypeError: If ``query``/``store``/``lexical``/``embedder`` are the
                wrong type.
            ValueError: If ``top_k`` or ``candidate_multiplier`` is not a
                positive integer.
        """
        if not isinstance(query, str):
            raise TypeError(f"HybridRetriever: query must be a str, got {type(query).__name__}")
        if not isinstance(store, VectorMemoryStore):
            raise TypeError(
                f"HybridRetriever: store must be a VectorMemoryStore, got {type(store).__name__}"
            )
        if not isinstance(lexical, Bm25Index):
            raise TypeError(
                f"HybridRetriever: lexical must be a Bm25Index, got {type(lexical).__name__}"
            )
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"HybridRetriever: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"HybridRetriever: top_k must be a positive int, got {top_k!r}")
        if not isinstance(candidate_multiplier, int) or candidate_multiplier <= 0:
            raise ValueError(
                f"HybridRetriever: candidate_multiplier must be a positive int, "
                f"got {candidate_multiplier!r}"
            )
        fetch = top_k * candidate_multiplier
        dense_ids, lexical_ids = await asyncio.gather(
            self._dense_ids(store, embedder, query, fetch),
            asyncio.to_thread(self._lexical_ids, lexical, query, fetch),
        )
        fused = reciprocal_rank_fusion([dense_ids, lexical_ids], k=rrf_k)
        return [{"id": identifier, "score": score} for identifier, score in fused[:top_k]]

    @staticmethod
    async def _dense_ids(
        store: VectorMemoryStore, embedder: EmbeddingProvider, query: str, fetch: int
    ) -> list[str]:
        """Embed ``query`` and return the dense-store ranked ids."""
        vectors = await embedder.embed([query])
        matches = await store.query(vectors[0], top_k=fetch)
        return [match.id for match in matches]

    @staticmethod
    def _lexical_ids(lexical: Bm25Index, query: str, fetch: int) -> list[str]:
        """Return the BM25 ranked ids (runs on a worker thread)."""
        return [doc_id for doc_id, _ in lexical.search(query, top_k=fetch)]
