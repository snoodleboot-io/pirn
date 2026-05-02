"""``_ChunkEmbedderStore`` — internal helper Knot for :class:`DocumentIngestionPipeline`.

Embeds each chunk and persists it under ``{doc_id}:{chunk_idx}`` in the
caller-supplied :class:`MemoryStore`. Internal API.
"""

from __future__ import annotations

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
        if not chunks:
            return 0
        doc_id = self._derive_doc_id(source)
        embeddings = await self._embedder.embed(chunks)
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                "DocumentIngestionPipeline: embedder returned "
                f"{len(embeddings)} vectors for {len(chunks)} chunks"
            )
        for index, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            key = f"{doc_id}:{index}"
            await self._store.store(
                key,
                {
                    "doc_id": doc_id,
                    "chunk_index": index,
                    "text": chunk,
                    "embedding": list(vector),
                },
            )
        return len(chunks)

    @staticmethod
    def _derive_doc_id(source: str) -> str:
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return digest[:16]
