"""Unit tests for :class:`EmbeddingIndexer`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing.embedding_indexer import (
    EmbeddingIndexer,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubEmbeddingProvider,
    StubMemoryStore,
)


class TestEmbeddingIndexerConstruction(unittest.TestCase):
    def test_rejects_non_embedding_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "EmbeddingProvider"):
            with Tapestry():
                EmbeddingIndexer(
                    chunks=["a"],
                    embedding_provider="not-a-provider",  # type: ignore[arg-type]
                    store=StubMemoryStore(hits=[]),
                    _config=KnotConfig(id="ei"),
                )

    def test_rejects_non_memory_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "MemoryStore"):
            with Tapestry():
                EmbeddingIndexer(
                    chunks=["a"],
                    embedding_provider=StubEmbeddingProvider(),
                    store="not-a-store",  # type: ignore[arg-type]
                    _config=KnotConfig(id="ei"),
                )


class TestEmbeddingIndexerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_zero(self) -> None:
        with Tapestry() as t:
            EmbeddingIndexer(
                chunks=[],
                embedding_provider=StubEmbeddingProvider(),
                store=StubMemoryStore(hits=[]),
                _config=KnotConfig(id="ei"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ei"] == 0

    async def test_returns_count_of_indexed_chunks(self) -> None:
        with Tapestry() as t:
            EmbeddingIndexer(
                chunks=["a", "b", "c"],
                embedding_provider=StubEmbeddingProvider(),
                store=StubMemoryStore(hits=[]),
                _config=KnotConfig(id="ei"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ei"] == 3

    async def test_raises_for_non_string_chunk(self) -> None:
        with Tapestry():
            with self.assertRaises(TypeError):
                EmbeddingIndexer(
                    chunks=["ok", 42],  # type: ignore[list-item]
                    embedding_provider=StubEmbeddingProvider(),
                    store=StubMemoryStore(hits=[]),
                    _config=KnotConfig(id="ei"),
                )
