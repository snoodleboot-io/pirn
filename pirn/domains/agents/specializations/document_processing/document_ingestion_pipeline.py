"""``DocumentIngestionPipeline`` — load, chunk, embed, store a document.

A :class:`SubTapestry` that takes a document source (file path or
``http``/``https`` URL), reads the text, splits it into overlapping
chunks, embeds each chunk via a caller-supplied
:class:`EmbeddingProvider`, and stores every embedding in a
:class:`MemoryStore` under a deterministic ``{doc_id}:{chunk_idx}`` key.

Returns the number of chunks stored. The deterministic key shape lets
downstream pipelines fetch chunks by index without scanning the store.

Algorithm:
    1. ``_DocumentLoader`` resolves the source (file path or HTTP/HTTPS URL) and
       returns the raw text string.
    2. ``_DocumentChunker`` partitions the text into overlapping windows of
       ``chunk_size`` characters with ``overlap`` stride.
    3. ``_ChunkEmbedderStore`` calls the ``EmbeddingProvider`` once per chunk, then
       writes each ``(embedding, text)`` pair to the ``MemoryStore`` under the key
       ``{doc_id}:{chunk_idx}``.
    4. The pipeline returns the total number of chunks written.

Math:
    Chunk count: ``ceil((len(text) - overlap) / (chunk_size - overlap))`` when
    ``chunk_size > overlap``; degenerate to ``ceil(len(text) / chunk_size)`` when
    ``overlap == 0``.

References:
    - Lewis et al., 2020 — RAG: Retrieval-Augmented Generation for
      Knowledge-Intensive NLP Tasks (arXiv 2005.11401).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.document_processing._chunk_embedder_store import (
    _ChunkEmbedderStore,
)
from pirn.domains.agents.specializations.document_processing._document_chunker import (
    _DocumentChunker,
)
from pirn.domains.agents.specializations.document_processing._document_loader import (
    _DocumentLoader,
)
from pirn.domains.ml.embedding_provider import EmbeddingProvider
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class DocumentIngestionPipeline(SubTapestry):
    """Load → chunk → embed → store; returns the number of chunks stored."""

    def __init__(
        self,
        *,
        source: Knot | str,
        embedder: Knot | EmbeddingProvider,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        chunk_size: Knot | int = 1000,
        chunk_overlap: Knot | int = 100,
        allowed_root: Knot | str | None = None,
        allowed_hosts: Knot | tuple[str, ...] | None = None,
        max_bytes: Knot | int = 100 * 1024 * 1024,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source=source,
            embedder=embedder,
            store=store,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            allowed_root=allowed_root,
            allowed_hosts=allowed_hosts,
            max_bytes=max_bytes,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        source: str,
        embedder: EmbeddingProvider,
        store: MemoryStore,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
        allowed_root: str | None = None,
        allowed_hosts: tuple[str, ...] | None = None,
        max_bytes: int = 100 * 1024 * 1024,
        **_: Any,
    ) -> int:
        """Load, chunk, embed, and store a document; return the number of chunks stored.

        Args:
            source: A local file path or http(s):// URL identifying the document to ingest.
            embedder: The embedding provider for producing chunk vectors.
            store: The memory store for persisting chunk embeddings.
            chunk_size: Maximum character length of each chunk.
            chunk_overlap: Number of overlapping characters between adjacent chunks.
            allowed_root: Directory root that local file reads must stay within.
            allowed_hosts: Optional allow-list of hostnames for URL fetches.
            max_bytes: Maximum file size in bytes.

        Returns:
            The number of chunks embedded and stored.

        Raises:
            TypeError: If source is not a non-empty string.
            ValueError: If chunk_size or chunk_overlap are invalid.
        """
        if not isinstance(source, str) or not source:
            raise TypeError(
                "DocumentIngestionPipeline: source must be a non-empty "
                f"string, got {source!r}"
            )
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ValueError(
                "DocumentIngestionPipeline: chunk_size must be a positive int, "
                f"got {chunk_size!r}"
            )
        if (
            not isinstance(chunk_overlap, int)
            or chunk_overlap < 0
            or chunk_overlap >= chunk_size
        ):
            raise ValueError(
                "DocumentIngestionPipeline: chunk_overlap must be a non-"
                "negative int strictly less than chunk_size, "
                f"got {chunk_overlap!r}"
            )
        with Tapestry() as inner:
            loaded = _DocumentLoader(
                source=source,
                allowed_root=allowed_root,
                allowed_hosts=allowed_hosts,
                max_bytes=max_bytes,
                _config=KnotConfig(id="load"),
            )
            chunks = _DocumentChunker(
                text=loaded,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                _config=KnotConfig(id="chunk"),
            )
            _ChunkEmbedderStore(
                chunks=chunks,
                source=source,
                embedder=embedder,
                store=store,
                _config=KnotConfig(id="store"),
            )
        inner_result = await self._run_inner(inner)
        count = inner_result.outputs.get("store")
        if not isinstance(count, int):
            return 0
        return count
