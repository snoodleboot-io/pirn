"""Tests for :class:`DocumentIngestionPipeline`."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.document_processing.document_ingestion_pipeline import (  # noqa: E501
    DocumentIngestionPipeline,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubEmbeddingProvider,
)


class _RecordingMemoryStore(MemoryStore):
    """In-memory store that records every :meth:`store` call."""

    def __init__(self) -> None:
        self.entries: dict[str, Mapping[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.entries[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self.entries.get(key)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
    ) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for entry in list(self.entries.values())[:top_k]:
                yield entry

        return _aiter()

    async def forget(self, key: str) -> None:
        self.entries.pop(key, None)

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
class TestDocumentIngestionPipelineConstruction:
    async def test_rejects_non_embedder(self) -> None:
        store = _RecordingMemoryStore()
        with pytest.raises(TypeError, match="embedder must be an EmbeddingProvider"):
            with Tapestry():
                DocumentIngestionPipeline(
                    source="/tmp/x.txt",
                    embedder="not-an-embedder",  # type: ignore[arg-type]
                    store=store,
                    _config=KnotConfig(id="ingest"),
                )

    async def test_rejects_overlap_ge_chunk_size(self) -> None:
        embedder = StubEmbeddingProvider()
        store = _RecordingMemoryStore()
        with pytest.raises(ValueError, match="chunk_overlap"):
            with Tapestry():
                DocumentIngestionPipeline(
                    source="/tmp/x.txt",
                    embedder=embedder,
                    store=store,
                    chunk_size=10,
                    chunk_overlap=10,
                    _config=KnotConfig(id="ingest"),
                )


@pytest.mark.asyncio
class TestDocumentIngestionPipelineHappyPath:
    async def test_chunks_embeds_and_stores(self, tmp_path: Path) -> None:
        document = tmp_path / "doc.txt"
        document.write_text("a" * 25, encoding="utf-8")
        embedder = StubEmbeddingProvider(dimension=3)
        store = _RecordingMemoryStore()
        with Tapestry() as t:
            DocumentIngestionPipeline(
                source=str(document),
                embedder=embedder,
                store=store,
                chunk_size=10,
                chunk_overlap=2,
                _config=KnotConfig(id="ingest"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        chunks_written = result.outputs["ingest"]
        assert chunks_written == len(store.entries)
        assert chunks_written >= 3
        first_key = sorted(store.entries.keys())[0]
        assert ":" in first_key
        first_entry = store.entries[first_key]
        assert "doc_id" in first_entry
        assert "embedding" in first_entry
        assert len(first_entry["embedding"]) == 3
