"""``_ChunkEmbedderStore`` — internal helper Knot for :class:`DocumentIngestionPipeline`.

Each chunk's persisted write is independent of every other chunk's, so
persisting them is a fan-out — one
:class:`~pirn_agents.specializations.document_processing._chunk_store_write._ChunkStoreWrite`
knot per chunk wired into an :class:`~pirn.nodes.aggregator.Aggregator` —
rather than a hand-rolled ``asyncio.gather`` over bare coroutines (PIR-867;
before this, no chunk's write had its own lineage row). The embedding call
itself stays a single batched call, since batching is the whole reason the
embedder gets every chunk at once rather than one at a time.

Algorithm:
    1. Receive resolved ``chunks``, ``source``, ``embedder``, and ``store``.
    2. When ``chunks`` is empty, return a ``Parameter`` defaulting to ``0``
       — an ``Aggregator`` requires at least one parent.
    3. Derive a deterministic ``doc_id`` from ``source`` via SHA-256 (first 16 hex chars).
    4. Call ``embedder.embed(chunks)`` in one batch.
    5. Validate vector count matches chunk count.
    6. Build one ``_ChunkStoreWrite`` per ``{doc_id}:{index}`` key and wire
       them as the parents of an ``Aggregator`` whose combine returns the
       chunk count.

Math:
    doc_id = SHA-256(source.encode("utf-8"))[:16]

References:
    - Python hashlib documentation for SHA-256.

Internal API.
"""

from __future__ import annotations

import functools
import hashlib
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.retrieval.embeddings.embedding_provider import EmbeddingProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.document_processing._chunk_store_write import (
    _ChunkStoreWrite,
)


class _ChunkEmbedderStore(AgentPipeline):
    """Embed each chunk and persist it under ``{doc_id}:{chunk_idx}``."""

    def __init__(
        self,
        *,
        chunks: Knot | list[str],
        source: Knot | str,
        embedder: Knot | EmbeddingProvider,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            chunks=chunks,
            source=source,
            embedder=embedder,
            store=store,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        chunks: list[str],
        source: str,
        embedder: EmbeddingProvider,
        store: MemoryStore,
        **_: Any,
    ) -> Knot:
        """Embed every chunk in one batch and wire one persist knot per chunk.

        Args:
            chunks: The list of text chunks to embed and persist.
            source: The source identifier used to derive the document ID for key generation.
            embedder: The embedding provider used to produce chunk vectors.
            store: The memory store used to persist chunk embeddings.

        Returns:
            The sink of the inner pipeline: a ``Parameter`` defaulting to
            ``0`` when ``chunks`` is empty, or an :class:`Aggregator` over
            one ``_ChunkStoreWrite`` per chunk whose output is the number of
            chunks stored.

        Raises:
            RuntimeError: If the embedder returns a different number of vectors than chunks.
        """
        if not chunks:
            return Parameter("empty", int, default=0, _config=KnotConfig(id="empty"))
        doc_id = self._derive_doc_id(source)
        embeddings = await embedder.embed(chunks)
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                "DocumentIngestionPipeline: embedder returned "
                f"{len(embeddings)} vectors for {len(chunks)} chunks"
            )
        per_chunk: dict[str, Knot] = {
            f"chunk_{index}": _ChunkStoreWrite(
                key=f"{doc_id}:{index}",
                payload={
                    "doc_id": doc_id,
                    "chunk_index": index,
                    "text": chunk,
                    "embedding": list(vector),
                },
                store=store,
                _config=KnotConfig(id=f"write_{index}"),
            )
            for index, (chunk, vector) in enumerate(zip(chunks, embeddings, strict=False))
        }
        return Aggregator(
            combine=functools.partial(self._count, len(chunks)),
            _config=KnotConfig(id="count"),
            **per_chunk,
        )

    @staticmethod
    def _count(count: int, **_: Any) -> int:
        """Ignore the individual write outcomes and return the chunk count."""
        return count

    @staticmethod
    def _derive_doc_id(source: str) -> str:
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return digest[:16]
