"""``ParentDocumentIngestor`` — small-to-big indexing at ingest time.

Parent-doc (a.k.a. small-to-big) retrieval indexes *small* child chunks for
precise matching but returns the *larger* parent for context. This ingestor
reuses the existing sliding-window
:class:`~pirn_agents.specializations.document_processing._document_chunker._DocumentChunker`
to split the document into children, then wires
:class:`~pirn_agents.specializations.rag.indexing._parent_child_indexer._ParentChildIndexer`
to group children under parents and upsert the child records.

References:
    - Small-to-big / parent-document retrieval (LlamaIndex, LangChain).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.specializations.document_processing._document_chunker import _DocumentChunker
from pirn_agents.specializations.rag.indexing._parent_child_indexer import _ParentChildIndexer
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore


class ParentDocumentIngestor(SubTapestry):
    """Chunk into children, then index them under grouped parents."""

    def __init__(
        self,
        *,
        text: Knot | str,
        embedder: Knot | EmbeddingProvider,
        store: Knot | VectorMemoryStore,
        doc_id: Knot | str,
        _config: KnotConfig,
        child_chunk_size: Knot | int = 200,
        chunk_overlap: Knot | int = 0,
        group_size: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            text=text,
            embedder=embedder,
            store=store,
            doc_id=doc_id,
            child_chunk_size=child_chunk_size,
            chunk_overlap=chunk_overlap,
            group_size=group_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        text: str,
        embedder: EmbeddingProvider,
        store: VectorMemoryStore,
        doc_id: str,
        child_chunk_size: int = 200,
        chunk_overlap: int = 0,
        group_size: int = 3,
        **_: Any,
    ) -> Any:
        """Wire ``_DocumentChunker`` → ``_ParentChildIndexer`` and return the sink.

        Args:
            text: The full source document to ingest.
            embedder: The provider embedding each child chunk.
            store: The vector store receiving the child records.
            doc_id: The source document id used for stable record keys.
            child_chunk_size: Character size of each child chunk.
            chunk_overlap: Character overlap between adjacent children.
            group_size: Number of consecutive children per parent.

        Returns:
            The ``_ParentChildIndexer`` sink knot whose output is the child count.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        if not isinstance(text, str):
            raise TypeError(
                f"ParentDocumentIngestor: text must be a string, got {type(text).__name__}"
            )
        chunks = _DocumentChunker(
            text=text,
            chunk_size=child_chunk_size,
            chunk_overlap=chunk_overlap,
            _config=KnotConfig(id="chunk"),
        )
        return _ParentChildIndexer(
            chunks=chunks,
            embedder=embedder,
            store=store,
            doc_id=doc_id,
            group_size=group_size,
            _config=KnotConfig(id="index"),
        )
