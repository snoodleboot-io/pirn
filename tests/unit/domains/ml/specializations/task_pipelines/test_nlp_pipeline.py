"""Unit tests for :class:`NLPPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.ml.embedding_provider import EmbeddingProvider
from pirn.domains.ml.specializations.task_pipelines.nlp_pipeline import NLPPipeline
from pirn.tapestry import Tapestry


class _StubPool(DatabaseConnectionPool):
    pass


class _StubProvider(EmbeddingProvider):
    async def embed(self, texts, *, model=None):
        return [[0.1, 0.2] for _ in texts]

    async def close(self) -> None:
        pass


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_text_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                NLPPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    text_column="",
                    target_column="label",
                    embedding_provider=_StubProvider(),
                    _config=KnotConfig(id="nlp"),
                )

    def test_rejects_wrong_provider_type(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                NLPPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    text_column="text",
                    target_column="label",
                    embedding_provider="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="nlp"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            NLPPipeline(
                pool=_StubPool(),
                query="SELECT * FROM data",
                text_column="review",
                target_column="label",
                embedding_provider=_StubProvider(),
                _config=KnotConfig(id="nlp"),
            )
        self.assertIsNotNone(t._store.get("nlp"))
