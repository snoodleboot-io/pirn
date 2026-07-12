"""``_ParentChildIndexer`` — index small child chunks under larger parents.

Internal terminal knot shared by the parent-doc and auto-merging ingestors. It
groups consecutive child chunks into parents, embeds every child, and upserts
each child as a :class:`VectorRecord` carrying the parent id, the full parent
text, and the parent's sibling count. Retrieval then matches precise children
but can return (or merge up to) the larger parent.

Algorithm:
    1. Validate ``chunks`` (list of str), ``embedder``, ``store``,
       ``group_size`` (positive int), and ``doc_id`` (str).
    2. Group consecutive children into parents of ``group_size``; the parent
       text is the newline-join of its children.
    3. Embed all child texts and upsert one record per child with metadata
       ``{parent_id, parent_text, sibling_count, child_index, kind}``.
    4. Return the number of child records written.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.embedding_provider import EmbeddingProvider

from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from pirn_agents.vector_stores.vector_record import VectorRecord


class _ParentChildIndexer(Knot):
    """Group children under parents, embed them, and upsert child records."""

    def __init__(
        self,
        *,
        chunks: Knot | list[str],
        embedder: Knot | EmbeddingProvider,
        store: Knot | VectorMemoryStore,
        doc_id: Knot | str,
        _config: KnotConfig,
        group_size: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            chunks=chunks,
            embedder=embedder,
            store=store,
            doc_id=doc_id,
            group_size=group_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        chunks: list[str],
        embedder: EmbeddingProvider,
        store: VectorMemoryStore,
        doc_id: str,
        group_size: int = 3,
        **_: Any,
    ) -> int:
        """Index children under parents and return the number of child records.

        Args:
            chunks: The child chunk texts to index.
            embedder: The provider embedding each child.
            store: The vector store receiving the child records.
            doc_id: The source document id used to build stable record keys.
            group_size: Number of consecutive children per parent.

        Returns:
            The number of child records upserted.

        Raises:
            TypeError: If ``embedder``/``store`` are the wrong type or ``doc_id``
                is not a string.
            ValueError: If ``group_size`` is not a positive integer.
        """
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"_ParentChildIndexer: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not isinstance(store, VectorMemoryStore):
            raise TypeError(
                f"_ParentChildIndexer: store must be a VectorMemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(doc_id, str):
            raise TypeError(
                f"_ParentChildIndexer: doc_id must be a string, got {type(doc_id).__name__}"
            )
        if not isinstance(group_size, int) or group_size <= 0:
            raise ValueError(
                f"_ParentChildIndexer: group_size must be a positive int, got {group_size!r}"
            )
        if not chunks:
            return 0
        vectors = await embedder.embed(list(chunks))
        records: list[VectorRecord] = []
        for child_index, child_text in enumerate(chunks):
            parent_index = child_index // group_size
            start = parent_index * group_size
            group = chunks[start : start + group_size]
            parent_text = "\n".join(group)
            records.append(
                VectorRecord.create(
                    id=f"{doc_id}:child:{child_index}",
                    vector=vectors[child_index],
                    metadata={
                        "parent_id": f"{doc_id}:parent:{parent_index}",
                        "parent_text": parent_text,
                        "sibling_count": len(group),
                        "child_index": child_index,
                        "kind": "child",
                    },
                    document=child_text,
                )
            )
        await store.upsert(records)
        return len(records)
