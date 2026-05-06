"""``EmbeddingIndexer`` — embed text chunks and store them in a MemoryStore.

A :class:`Knot` that takes a list of text chunk strings, calls an
:class:`EmbeddingProvider` to produce embedding vectors, stores each
chunk together with its vector in a :class:`MemoryStore`, and returns
the total count of indexed chunks.

Algorithm:
    1. Iterate over the input ``chunks`` sequence in order.
    2. For each chunk at index ``i``, call ``EmbeddingProvider.embed(chunk)`` to
       obtain a dense float vector.
    3. Write the ``(vector, text)`` pair to the ``MemoryStore`` under the key
       supplied by the caller (typically ``{doc_id}:{i}``).
    4. Return the total number of chunks written as an integer.

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
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.ml.embedding_provider import EmbeddingProvider


class EmbeddingIndexer(Knot):
    """Embed text chunks and persist them in a MemoryStore."""

    def __init__(
        self,
        *,
        chunks: Knot | Sequence[str],
        embedding_provider: Knot | EmbeddingProvider,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            chunks=chunks, embedding_provider=embedding_provider, store=store,
            _config=_config, **kwargs,
        )

    async def process(
        self,
        chunks: Sequence[str],
        embedding_provider: EmbeddingProvider,
        store: MemoryStore,
        **_: Any,
    ) -> int:
        """Embed each chunk and store it; return the count of indexed chunks.

        Args:
            chunks: A sequence of text chunk strings to embed and index.
            embedding_provider: The embedding provider to produce chunk vectors.
            store: The memory store to persist chunk embeddings.

        Returns:
            The number of chunks successfully indexed.

        Raises:
            TypeError: If any element of chunks is not a string.
        """
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
        for index, (chunk, vector) in enumerate(
            zip(chunk_list, vectors, strict=True)
        ):
            await store.store(
                f"chunk_{index}",
                {"text": chunk, "embedding": vector},
            )
        return len(chunk_list)
