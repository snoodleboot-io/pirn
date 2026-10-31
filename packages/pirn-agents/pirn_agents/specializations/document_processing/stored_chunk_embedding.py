"""``StoredChunkEmbedding`` — persist one chunk and its embedding, and return its key.

One knot per chunk, so each write has its own ``Result``, retry, timeout and
lineage row rather than being one turn of a Python loop the run cannot see — the
shape :class:`~pirn_agents.memory.patterns.stored_semantic_fact.StoredSemanticFact`
already uses for facts (PIR-874).

Internal API. See ``embedding_indexer.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.stores.memory_store import MemoryStore


class StoredChunkEmbedding(Knot):
    """Write one chunk's text and embedding into a store under its indexed key."""

    def __init__(
        self,
        *,
        document_id: Knot | str,
        chunk_index: Knot | int,
        text: Knot | str,
        embedding: Knot | Sequence[float],
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            document_id=document_id,
            chunk_index=chunk_index,
            text=text,
            embedding=embedding,
            store=store,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        document_id: str,
        chunk_index: int,
        text: str,
        embedding: Sequence[float],
        store: MemoryStore,
        **_: Any,
    ) -> str:
        """Write this chunk under ``"<document_id>:<chunk_index>"`` and return that key.

        Args:
            document_id: The document the chunk belongs to.
            chunk_index: The chunk's position in the document.
            text: The chunk's text.
            embedding: The chunk's embedding vector.
            store: The store to write into.

        Returns:
            The key the chunk was written under.
        """
        key = f"{document_id}:{chunk_index}"
        await store.store(
            key,
            {
                "doc_id": document_id,
                "chunk_index": chunk_index,
                "text": text,
                "embedding": list(embedding),
            },
        )
        return key
