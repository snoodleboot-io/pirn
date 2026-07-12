"""``RaptorTreeBuilder`` — chunk a document and build its RAPTOR tree.

A :class:`SubTapestry` that reuses the existing sliding-window
:class:`~pirn_agents.specializations.document_processing._document_chunker._DocumentChunker`
to produce leaf chunks, then wires
:class:`~pirn_agents.specializations.rag.indexing._raptor_assembler._RaptorAssembler`
to cluster + summarize them into a content-addressed RAPTOR tree stored in the
vector store. The tree is built once at ingest and reused across queries.

References:
    - Sarthi et al., "RAPTOR" (ICLR 2024): https://arxiv.org/abs/2401.18059
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.embedding_provider import EmbeddingProvider
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.document_processing._document_chunker import _DocumentChunker
from pirn_agents.specializations.rag.indexing._raptor_assembler import _RaptorAssembler
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore


class RaptorTreeBuilder(SubTapestry):
    """Chunk a document, then build (or reuse) its RAPTOR summary tree."""

    def __init__(
        self,
        *,
        text: Knot | str,
        llm: Knot | LLMProvider,
        embedder: Knot | EmbeddingProvider,
        store: Knot | VectorMemoryStore,
        _config: KnotConfig,
        leaf_chunk_size: Knot | int = 120,
        chunk_overlap: Knot | int = 0,
        cluster_size: Knot | int = 2,
        max_levels: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            text=text,
            llm=llm,
            embedder=embedder,
            store=store,
            leaf_chunk_size=leaf_chunk_size,
            chunk_overlap=chunk_overlap,
            cluster_size=cluster_size,
            max_levels=max_levels,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        text: str,
        llm: LLMProvider,
        embedder: EmbeddingProvider,
        store: VectorMemoryStore,
        leaf_chunk_size: int = 120,
        chunk_overlap: int = 0,
        cluster_size: int = 2,
        max_levels: int = 3,
        **_: Any,
    ) -> Any:
        """Wire ``_DocumentChunker`` → ``_RaptorAssembler`` and return the sink.

        Args:
            text: The full source document to build a tree from.
            llm: The provider summarizing clusters.
            embedder: The provider embedding nodes.
            store: The vector store receiving the tree.
            leaf_chunk_size: Character size of each leaf chunk.
            chunk_overlap: Character overlap between adjacent leaves.
            cluster_size: Number of consecutive nodes per cluster.
            max_levels: Maximum number of summary levels above the leaves.

        Returns:
            The ``_RaptorAssembler`` sink knot whose output is the :class:`RaptorTree`.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        if not isinstance(text, str):
            raise TypeError(f"RaptorTreeBuilder: text must be a string, got {type(text).__name__}")
        chunks = _DocumentChunker(
            text=text,
            chunk_size=leaf_chunk_size,
            chunk_overlap=chunk_overlap,
            _config=KnotConfig(id="chunk"),
        )
        return _RaptorAssembler(
            chunks=chunks,
            llm=llm,
            embedder=embedder,
            store=store,
            cluster_size=cluster_size,
            max_levels=max_levels,
            _config=KnotConfig(id="assemble"),
        )
