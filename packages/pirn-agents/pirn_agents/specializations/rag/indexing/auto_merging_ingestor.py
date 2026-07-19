"""``AutoMergingIngestor`` — index leaf chunks under mergeable parents.

Auto-merging retrieval indexes fine-grained leaf chunks but merges them back up
to their parent at query time when enough leaves of one parent are retrieved
together. Ingest is structurally identical to parent-doc — this ingestor reuses
the existing sliding-window
:class:`~pirn_agents.specializations.document_processing._document_chunker._DocumentChunker`
and the shared
:class:`~pirn_agents.specializations.rag.indexing._parent_child_indexer._ParentChildIndexer`;
the merge behaviour lives in :class:`AutoMergingRetriever`.

References:
    - Auto-merging retriever (LlamaIndex).
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


class AutoMergingIngestor(SubTapestry):
    """Chunk into leaves and index them under mergeable parents."""

    def __init__(
        self,
        *,
        text: Knot | str,
        embedder: Knot | EmbeddingProvider,
        store: Knot | VectorMemoryStore,
        doc_id: Knot | str,
        _config: KnotConfig,
        leaf_chunk_size: Knot | int = 120,
        chunk_overlap: Knot | int = 0,
        group_size: Knot | int = 4,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            text=text,
            embedder=embedder,
            store=store,
            doc_id=doc_id,
            leaf_chunk_size=leaf_chunk_size,
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
        leaf_chunk_size: int = 120,
        chunk_overlap: int = 0,
        group_size: int = 4,
        **_: Any,
    ) -> Any:
        """Wire ``_DocumentChunker`` → ``_ParentChildIndexer`` and return the sink.

        Args:
            text: The full source document to ingest.
            embedder: The provider embedding each leaf chunk.
            store: The vector store receiving the leaf records.
            doc_id: The source document id used for stable record keys.
            leaf_chunk_size: Character size of each leaf chunk.
            chunk_overlap: Character overlap between adjacent leaves.
            group_size: Number of consecutive leaves per parent.

        Returns:
            The ``_ParentChildIndexer`` sink knot whose output is the leaf count.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        if not isinstance(text, str):
            raise TypeError(
                f"AutoMergingIngestor: text must be a string, got {type(text).__name__}"
            )
        chunks = _DocumentChunker(
            text=text,
            chunk_size=leaf_chunk_size,
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
