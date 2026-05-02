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

import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.ml.embedding_provider import EmbeddingProvider
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class _DocumentLoader(Knot):
    """Read text from a local file path or fetch it over HTTP(S)."""

    def __init__(
        self,
        *,
        source: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(source=source, _config=_config, **kwargs)

    async def process(self, source: str, **_: Any) -> str:
        if not isinstance(source, str) or not source:
            raise TypeError(
                "DocumentIngestionPipeline: source must be a non-empty "
                f"string, got {source!r}"
            )
        parsed = urlparse(source)
        if parsed.scheme in ("http", "https"):
            return await self._fetch_url(source)
        return self._read_file(source)

    @staticmethod
    def _read_file(path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    @staticmethod
    async def _fetch_url(url: str) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "DocumentIngestionPipeline: http(s) sources require httpx; "
                "install via `pip install pirn[http]`"
            ) from exc
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text


class _DocumentChunker(Knot):
    """Split text into overlapping fixed-size chunks."""

    def __init__(
        self,
        *,
        text: Knot | str,
        chunk_size: int,
        chunk_overlap: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            text=text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
        **_: Any,
    ) -> list[str]:
        if chunk_size <= 0:
            raise ValueError(
                "DocumentIngestionPipeline: chunk_size must be positive, "
                f"got {chunk_size!r}"
            )
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError(
                "DocumentIngestionPipeline: chunk_overlap must be in "
                f"[0, chunk_size), got {chunk_overlap!r}"
            )
        if not text:
            return []
        stride = chunk_size - chunk_overlap
        chunks: list[str] = []
        position = 0
        length = len(text)
        while position < length:
            end = min(position + chunk_size, length)
            chunks.append(text[position:end])
            if end == length:
                break
            position += stride
        return chunks


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
