"""``SentenceWindowRetriever`` — match a sentence, return its window.

The retrieval half of sentence-window. It embeds the query, matches the most
relevant single sentences, and returns each hit's stored neighbour *window* as
the context text (keeping the matched sentence itself for reference).

Algorithm:
    1. Validate ``query`` (str), ``store`` (:class:`VectorMemoryStore`),
       ``embedder`` (:class:`EmbeddingProvider`), and ``top_k`` (positive int).
    2. Embed the query and match ``top_k`` sentence records.
    3. Return each hit as ``{"id", "text": window, "sentence": doc, "score"}``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore


class SentenceWindowRetriever(Knot):
    """Match precise sentences and return their surrounding windows."""

    def __init__(
        self,
        *,
        query: Knot | str,
        store: Knot | VectorMemoryStore,
        embedder: Knot | EmbeddingProvider,
        _config: KnotConfig,
        top_k: Knot | int = 3,
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
        top_k: int = 3,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Return up to ``top_k`` matched sentences expanded to their windows.

        Args:
            query: The user query.
            store: The vector store holding sentence records.
            embedder: The provider embedding the query.
            top_k: Number of sentence hits to return.

        Returns:
            Hit mappings ``{"id", "text": window, "sentence": doc, "score"}``.

        Raises:
            TypeError: If ``query``/``store``/``embedder`` are the wrong type.
            ValueError: If ``top_k`` is not a positive integer.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"SentenceWindowRetriever: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(store, VectorMemoryStore):
            raise TypeError(
                f"SentenceWindowRetriever: store must be a VectorMemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"SentenceWindowRetriever: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                f"SentenceWindowRetriever: top_k must be a positive int, got {top_k!r}"
            )
        vectors = await embedder.embed([query])
        matches = await store.query(vectors[0], top_k=top_k)
        results: list[Mapping[str, Any]] = []
        for match in matches:
            window = match.metadata.get("window")
            text = window if isinstance(window, str) else (match.document or "")
            results.append(
                {
                    "id": match.id,
                    "text": text,
                    "sentence": match.document or "",
                    "score": match.score,
                }
            )
        return results
