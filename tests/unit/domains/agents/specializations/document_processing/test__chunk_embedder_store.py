"""Unit tests for :class:`_ChunkEmbedderStore`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing._chunk_embedder_store import (
    _ChunkEmbedderStore,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubEmbeddingProvider,
    StubMemoryStore,
)


class _StrSource:
    pass


class TestChunkEmbedderStoreProcess(unittest.IsolatedAsyncioTestCase):
    async def _run(self, chunks, source="doc.txt"):
        embedder = StubEmbeddingProvider(dimension=4)
        store = StubMemoryStore(hits=[])
        stored_keys: list[str] = []
        stored_payloads: list[dict] = []

        original_store = store.store

        async def _capture(key, value):
            stored_keys.append(key)
            stored_payloads.append(dict(value))
            return await original_store(key, value)

        store.store = _capture  # type: ignore[assignment]

        with Tapestry() as t:
            _ChunkEmbedderStore(
                chunks=chunks,
                source=source,
                embedder=embedder,
                store=store,
                _config=KnotConfig(id="ces"),
            )
        result = await t.run(RunRequest())
        return result, stored_keys, stored_payloads, embedder

    async def test_empty_chunks_returns_zero(self) -> None:
        with Tapestry() as t:
            _ChunkEmbedderStore(
                chunks=[],
                source="x",
                embedder=StubEmbeddingProvider(),
                store=StubMemoryStore(hits=[]),
                _config=KnotConfig(id="ces"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ces"] == 0

    async def test_stores_correct_count(self) -> None:
        result, keys, payloads, _ = await self._run(["alpha", "beta"])
        assert result.outputs["ces"] == 2
        assert len(keys) == 2

    async def test_keys_follow_doc_id_pattern(self) -> None:
        _, keys, _, _ = await self._run(["hello"], source="my_doc")
        assert ":" in keys[0]

    async def test_payload_contains_text_and_embedding(self) -> None:
        _, keys, payloads, _ = await self._run(["chunk_text"])
        assert payloads[0]["text"] == "chunk_text"
        assert "embedding" in payloads[0]

    async def test_raises_when_embedder_returns_wrong_count(self) -> None:
        class MismatchEmbedder(StubEmbeddingProvider):
            async def embed(self, texts, *, model=None):
                return []  # always returns 0 vectors

        with Tapestry() as t:
            _ChunkEmbedderStore(
                chunks=["a", "b"],
                source="x",
                embedder=MismatchEmbedder(),
                store=StubMemoryStore(hits=[]),
                _config=KnotConfig(id="ces"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
