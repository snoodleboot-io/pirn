"""``EmbeddingIndexer`` — embed text chunks and store them in a MemoryStore.

A :class:`Knot` that takes a list of text chunk strings belonging to one
document, calls an :class:`EmbeddingProvider` to produce embedding vectors,
stores each chunk together with its vector in a :class:`MemoryStore` under a
document-scoped key, and returns the total count of indexed chunks.

Records are keyed ``{document_id}:{index}`` — the same scheme
:class:`~pirn_agents.specializations.document_processing.chunk_embedder_store.ChunkEmbedderStore`
uses — so indexing a second document into the same store never overwrites the
first document's chunks.

Algorithm:
    1. Validate ``document_id`` is a non-empty string and every chunk is a string.
    2. Return ``0`` when ``chunks`` is empty.
    3. Call ``EmbeddingProvider.embed(chunks)`` once to obtain one dense float
       vector per chunk.
    4. For each chunk at index ``i``, write
       ``{"doc_id": document_id, "chunk_index": i, "text": chunk, "embedding": vector}``
       to the ``MemoryStore`` under the key ``{document_id}:{i}``.
    5. Return the total number of chunks written as an integer.

Math:
    No mathematical computation performed here — the embedding arithmetic is
    delegated entirely to the ``EmbeddingProvider`` implementation. The count
    returned equals ``len(chunks)``.

References:
    - Reimers & Gurevych, 2019 — Sentence-BERT: Sentence Embeddings using
      Siamese BERT-Networks (arXiv 1908.10084).
    - Lewis et al., 2020 — RAG: Retrieval-Augmented Generation for
      Knowledge-Intensive NLP Tasks (arXiv 2005.11401).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.retrieval.embeddings.embedding_provider import EmbeddingProvider


class EmbeddingIndexer(Knot):
    """Embed text chunks and persist them in a MemoryStore."""

    def __init__(
        self,
        *,
        chunks: Knot | Sequence[str],
        document_id: Knot | str,
        embedding_provider: Knot | EmbeddingProvider,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            chunks=chunks,
            document_id=document_id,
            embedding_provider=embedding_provider,
            store=store,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        chunks: Sequence[str],
        document_id: str,
        embedding_provider: EmbeddingProvider,
        store: MemoryStore,
        **_: Any,
    ) -> int:
        """Embed each chunk and store it; return the count of indexed chunks.

        Args:
            chunks: A sequence of text chunk strings to embed and index.
            document_id: Identifier of the document the chunks belong to; it
                scopes every record key (``{document_id}:{index}``).
            embedding_provider: The embedding provider to produce chunk vectors.
            store: The memory store to persist chunk embeddings.

        Returns:
            The number of chunks successfully indexed.

        Raises:
            TypeError: If ``document_id`` or any element of chunks is not a string.
            ValueError: If ``document_id`` is empty.
        """
        if not isinstance(document_id, str):
            raise TypeError(
                f"EmbeddingIndexer: document_id must be a string, got {type(document_id).__name__}"
            )
        if not document_id:
            raise ValueError("EmbeddingIndexer: document_id must be a non-empty string")
        for index, chunk in enumerate(chunks):
            if not isinstance(chunk, str):
                raise TypeError(
                    f"EmbeddingIndexer: chunks[{index}] must be a string, "
                    f"got {type(chunk).__name__}"
                )
        if not chunks:
            return 0
        chunk_list = list(chunks)
        vectors = await embedding_provider.embed(chunk_list)
        for index, (chunk, vector) in enumerate(zip(chunk_list, vectors, strict=True)):
            await store.store(
                f"{document_id}:{index}",
                {
                    "doc_id": document_id,
                    "chunk_index": index,
                    "text": chunk,
                    "embedding": list(vector),
                },
            )
        return len(chunk_list)
