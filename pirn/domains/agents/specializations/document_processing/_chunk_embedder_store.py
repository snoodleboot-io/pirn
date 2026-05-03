"""``_ChunkEmbedderStore`` — internal helper Knot for :class:`DocumentIngestionPipeline`.

Embeds each chunk and persists it under ``{doc_id}:{chunk_idx}`` in the
caller-supplied :class:`MemoryStore`. Internal API.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.ml.embedding_provider import EmbeddingProvider


class _ChunkEmbedderStore(Knot):
    """Embed each chunk and persist it under ``{doc_id}:{chunk_idx}``."""

    def __init__(
        self,
        *,
        chunks: Knot,
        source: Knot | str,
        embedder: EmbeddingProvider,
        store: MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._embedder = embedder
        self._store = store
        super().__init__(chunks=chunks, source=source, _config=_config, **kwargs)

    async def process(
        self,
        chunks: list[str],
        source: str,
        **_: Any,
    ) -> int:
        """Embed each text chunk and persist it in the store, returning the number stored.

        Args:
            chunks: The list of text chunks to embed and persist.
            source: The source identifier used to derive the document ID for key generation.

        Returns:
            The number of chunks embedded and stored.

        Raises:
            RuntimeError: If the embedder returns a different number of vectors than chunks.
        """
        if not chunks:
            return 0
        doc_id = self._derive_doc_id(source)
        embeddings = await self._embedder.embed(chunks)
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                "DocumentIngestionPipeline: embedder returned "
                f"{len(embeddings)} vectors for {len(chunks)} chunks"
            )
        # TODO: expose ``concurrency_limit`` constructor arg for
        # rate-sensitive vector stores (use ``asyncio.Semaphore``).
        await asyncio.gather(
            *(
                self._store.store(
                    f"{doc_id}:{index}",
                    {
                        "doc_id": doc_id,
                        "chunk_index": index,
                        "text": chunk,
                        "embedding": list(vector),
                    },
                )
                for index, (chunk, vector) in enumerate(zip(chunks, embeddings))
            )
        )
        return len(chunks)

    @staticmethod
    def _derive_doc_id(source: str) -> str:
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return digest[:16]
