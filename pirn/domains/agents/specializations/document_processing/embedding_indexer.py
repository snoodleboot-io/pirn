"""``EmbeddingIndexer`` — embed text chunks and store them in a MemoryStore.

A :class:`Knot` that takes a list of text chunk strings, calls an
:class:`EmbeddingProvider` to produce embedding vectors, stores each
chunk together with its vector in a :class:`MemoryStore`, and returns
the total count of indexed chunks.
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
        embedding_provider: EmbeddingProvider,
        store: MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(embedding_provider, EmbeddingProvider):
            raise TypeError(
                "EmbeddingIndexer: embedding_provider must be an "
                f"EmbeddingProvider, got {type(embedding_provider).__name__}"
            )
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "EmbeddingIndexer: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        self._embedding_provider = embedding_provider
        self._store = store
        super().__init__(chunks=chunks, _config=_config, **kwargs)

    async def process(
        self,
        chunks: Sequence[str],
        **_: Any,
    ) -> int:
        """Embed each chunk and store it; return the count of indexed chunks.

        Args:
            chunks: A sequence of text chunk strings to embed and index.

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
        vectors = await self._embedding_provider.embed(chunk_list)
        for index, (chunk, vector) in enumerate(
            zip(chunk_list, vectors, strict=True)
        ):
            await self._store.store(
                f"chunk_{index}",
                {"text": chunk, "embedding": vector},
            )
        return len(chunk_list)
