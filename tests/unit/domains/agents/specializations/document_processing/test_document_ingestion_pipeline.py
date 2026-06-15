"""Tests for :class:`DocumentIngestionPipeline`."""

from __future__ import annotations

import tempfile
import unittest
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.document_processing.document_ingestion_pipeline import (
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

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for entry in list(self.entries.values())[:top_k]:
                yield entry

        return _aiter()

    async def forget(self, key: str) -> None:
        self.entries.pop(key, None)

    async def close(self) -> None:
        return None


def _make_knot(embedder: StubEmbeddingProvider, store: _RecordingMemoryStore) -> DocumentIngestionPipeline:
    with Tapestry():
        return DocumentIngestionPipeline(
            source="/tmp/placeholder.txt",
            embedder=embedder,
            store=store,
            _config=KnotConfig(id="ingest"),
        )


class TestDocumentIngestionPipelineProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_chunk_overlap(self) -> None:
        embedder = StubEmbeddingProvider()
        store = _RecordingMemoryStore()
        k = _make_knot(embedder, store)
        with self.assertRaisesRegex(ValueError, "chunk_overlap"):
            await k.process(
                source="/tmp/x.txt",
                embedder=embedder,
                store=store,
                chunk_size=10,
                chunk_overlap=10,
            )

    async def test_chunks_embeds_and_stores(self) -> None:
        from pirn.core.run_request import RunRequest

        _td = tempfile.TemporaryDirectory()
        self.addCleanup(_td.cleanup)
        tmp_path = Path(_td.name)
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
                allowed_root=str(tmp_path),
                _config=KnotConfig(id="ingest"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        chunks_written = run.outputs["ingest"]
        assert chunks_written == len(store.entries)
        assert chunks_written >= 3
        first_key = sorted(store.entries.keys())[0]
        assert ":" in first_key
        first_entry = store.entries[first_key]
        assert "doc_id" in first_entry
        assert "embedding" in first_entry
        assert len(first_entry["embedding"]) == 3
