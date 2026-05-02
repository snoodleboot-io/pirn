"""``DocumentIngestionPipeline`` — load, chunk, embed, store a document.

A :class:`SubTapestry` that takes a document source (file path or
``http``/``https`` URL), reads the text, splits it into overlapping
chunks, embeds each chunk via a caller-supplied
:class:`EmbeddingProvider`, and stores every embedding in a
:class:`MemoryStore` under a deterministic ``{doc_id}:{chunk_idx}`` key.

Returns the number of chunks stored. The deterministic key shape lets
downstream pipelines fetch chunks by index without scanning the store.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.document_processing._chunk_embedder_store import (  # noqa: E501
    _ChunkEmbedderStore,
)
from pirn.domains.agents.specializations.document_processing._document_chunker import (  # noqa: E501
    _DocumentChunker,
)
from pirn.domains.agents.specializations.document_processing._document_loader import (  # noqa: E501
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
        embedder: EmbeddingProvider,
        store: MemoryStore,
        _config: KnotConfig,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
        allowed_root: str | None = None,
        allowed_hosts: tuple[str, ...] | None = None,
        max_bytes: int = 100 * 1024 * 1024,
        **kwargs: Any,
    ) -> None:
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                "DocumentIngestionPipeline: embedder must be an "
                f"EmbeddingProvider, got {type(embedder).__name__}"
            )
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "DocumentIngestionPipeline: store must be a MemoryStore, "
                f"got {type(store).__name__}"
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
        self._embedder = embedder
        self._store = store
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._allowed_root = allowed_root
        self._allowed_hosts = allowed_hosts
        self._max_bytes = max_bytes
        super().__init__(source=source, _config=_config, **kwargs)

    async def process(self, source: str, **_: Any) -> int:
        if not isinstance(source, str) or not source:
            raise TypeError(
                "DocumentIngestionPipeline: source must be a non-empty "
                f"string, got {source!r}"
            )
        with Tapestry() as inner:
            loaded = _DocumentLoader(
                source=source,
                allowed_root=self._allowed_root,
                allowed_hosts=self._allowed_hosts,
                max_bytes=self._max_bytes,
                _config=KnotConfig(id="load"),
            )
            chunks = _DocumentChunker(
                text=loaded,
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
                _config=KnotConfig(id="chunk"),
            )
            _ChunkEmbedderStore(
                chunks=chunks,
                source=source,
                embedder=self._embedder,
                store=self._store,
                _config=KnotConfig(id="store"),
            )
        inner_result = await self._run_inner(inner)
        count = inner_result.outputs.get("store")
        if not isinstance(count, int):
            return 0
        return count
