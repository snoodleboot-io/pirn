"""``_DenseIds`` — embed a query and rank the dense-store arm's candidate ids.

Internal per-arm knot for
:class:`~pirn_agents.retrieval.hybrid_retriever.HybridRetriever`'s fan-out
(PIR-867): the dense and lexical arms are independent of each other, so each
is its own node wired into an :class:`~pirn.nodes.aggregator.Aggregator`
rather than both being awaited together by hand under ``asyncio.gather``.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.retrieval.embeddings.embedding_provider import EmbeddingProvider
from pirn_agents.retrieval.vector_stores.vector_memory_store import VectorMemoryStore


class _DenseIds(Knot):
    """Embed ``query`` and return the dense-store's top ``fetch`` ranked ids."""

    def __init__(
        self,
        *,
        store: Knot | VectorMemoryStore,
        embedder: Knot | EmbeddingProvider,
        query: Knot | str,
        fetch: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            store=store, embedder=embedder, query=query, fetch=fetch, _config=_config, **kwargs
        )

    async def process(
        self,
        store: VectorMemoryStore,
        embedder: EmbeddingProvider,
        query: str,
        fetch: int,
        **_: Any,
    ) -> list[str]:
        """Return the dense-store ranked ids for ``query``, most similar first."""
        vectors = await embedder.embed([query])
        matches = await store.query(vectors[0], top_k=fetch)
        return [match.id for match in matches]
