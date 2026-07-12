"""``SelfQueryRetriever`` — vector search under an extracted metadata filter.

The retrieval stage of self-query RAG. It embeds the semantic query and issues a
:meth:`VectorMemoryStore.query` with the extracted ``metadata_filter`` applied as
a pre-filter (F4 metadata-filter support), so only records satisfying the
structured constraints are scored.

Algorithm:
    1. Validate ``query_spec`` (mapping with ``query`` + ``metadata_filter``),
       ``store`` (:class:`VectorMemoryStore`), ``embedder``
       (:class:`EmbeddingProvider`), and ``top_k`` (positive int).
    2. Embed the semantic query.
    3. Call ``store.query(vector, top_k=..., metadata_filter=...)``.
    4. Return each :class:`VectorMatch` as a plain mapping.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.embedding_provider import EmbeddingProvider

from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore


class SelfQueryRetriever(Knot):
    """Embed the semantic query and search under the extracted metadata filter."""

    def __init__(
        self,
        *,
        query_spec: Knot | Mapping[str, Any],
        store: Knot | VectorMemoryStore,
        embedder: Knot | EmbeddingProvider,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query_spec=query_spec,
            store=store,
            embedder=embedder,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query_spec: Mapping[str, Any],
        store: VectorMemoryStore,
        embedder: EmbeddingProvider,
        top_k: int = 5,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Retrieve ``top_k`` records matching the semantic query and metadata filter.

        Args:
            query_spec: A mapping carrying ``query`` (semantic text) and
                ``metadata_filter`` (the pre-filter to apply).
            store: The vector store to query.
            embedder: The provider used to embed the semantic query.
            top_k: Number of hits to return.

        Returns:
            The matched records as ``{"id", "score", "metadata", "document"}`` mappings.

        Raises:
            TypeError: If ``store``/``embedder`` are the wrong type or ``query_spec``
                is not a mapping.
            ValueError: If ``top_k`` is not a positive integer.
        """
        if not isinstance(store, VectorMemoryStore):
            raise TypeError(
                f"SelfQueryRetriever: store must be a VectorMemoryStore, got {type(store).__name__}"
            )
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"SelfQueryRetriever: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not isinstance(query_spec, Mapping):
            raise TypeError(
                f"SelfQueryRetriever: query_spec must be a Mapping, got {type(query_spec).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"SelfQueryRetriever: top_k must be a positive int, got {top_k!r}")
        semantic_query = str(query_spec.get("query", ""))
        raw_filter = query_spec.get("metadata_filter")
        metadata_filter = raw_filter if isinstance(raw_filter, Mapping) else None
        vectors = await embedder.embed([semantic_query])
        matches = await store.query(vectors[0], top_k=top_k, metadata_filter=metadata_filter)
        return [
            {
                "id": match.id,
                "score": match.score,
                "metadata": dict(match.metadata),
                "document": match.document,
            }
            for match in matches
        ]
