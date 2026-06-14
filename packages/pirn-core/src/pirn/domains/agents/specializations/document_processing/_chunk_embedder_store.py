"""``_ChunkEmbedderStore`` — internal helper Knot for :class:`DocumentIngestionPipeline`.

Algorithm:
    1. Receive resolved ``chunks``, ``source``, ``embedder``, and ``store``.
    2. Derive a deterministic ``doc_id`` from ``source`` via SHA-256 (first 16 hex chars).
    3. Call ``embedder.embed(chunks)`` in one batch.
    4. Validate vector count matches chunk count.
    5. Persist each ``{doc_id}:{index}`` key concurrently via ``asyncio.gather``.
    6. Return the number of chunks stored.

Math:
    doc_id = SHA-256(source.encode("utf-8"))[:16]

References:
    - Python hashlib documentation for SHA-256.

Internal API.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.embedding_provider import EmbeddingProvider
from pirn.domains.agents.memory_store import MemoryStore


class _ChunkEmbedderStore(Knot):
    """Embed each chunk and persist it under ``{doc_id}:{chunk_idx}``."""

    def __init__(
        self,
        *,
        chunks: Knot,
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
    ) -> int:
        """Embed each text chunk and persist it in the store, returning the number stored.

        Args:
            chunks: The list of text chunks to embed and persist.
            source: The source identifier used to derive the document ID for key generation.
            embedder: The embedding provider used to produce chunk vectors.
            store: The memory store used to persist chunk embeddings.

        Returns:
            The number of chunks embedded and stored.

        Raises:
            RuntimeError: If the embedder returns a different number of vectors than chunks.
        """
        if not chunks:
            return 0
        doc_id = self._derive_doc_id(source)
        embeddings = await embedder.embed(chunks)
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                "DocumentIngestionPipeline: embedder returned "
                f"{len(embeddings)} vectors for {len(chunks)} chunks"
            )
        # TODO: expose ``concurrency_limit`` constructor arg for
        # rate-sensitive vector stores (use ``asyncio.Semaphore``).
        await asyncio.gather(
            *(
                store.store(
                    f"{doc_id}:{index}",
                    {
                        "doc_id": doc_id,
                        "chunk_index": index,
                        "text": chunk,
                        "embedding": list(vector),
                    },
                )
                for index, (chunk, vector) in enumerate(zip(chunks, embeddings, strict=False))
            )
        )
        return len(chunks)

    @staticmethod
    def _derive_doc_id(source: str) -> str:
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return digest[:16]
