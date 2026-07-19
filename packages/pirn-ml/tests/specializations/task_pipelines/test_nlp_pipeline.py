"""Unit tests for :class:`NLPPipeline`."""

from __future__ import annotations

import unittest

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot_config import KnotConfig

from pirn_ml.embedding_provider import EmbeddingProvider
from pirn_ml.specializations.task_pipelines.nlp_pipeline import NLPPipeline


class _StubPool(DatabaseConnectionPool):
    pass


class _StubProvider(EmbeddingProvider):
    async def embed(self, texts, *, model=None):
        return [[0.1, 0.2] for _ in texts]

    async def close(self) -> None:
        pass


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_text_column(self) -> None:
        knot = NLPPipeline(
            pool=_StubPool(),
            query="SELECT 1",
            text_column="",
            target_column="label",
            embedding_provider=_StubProvider(),
            _config=KnotConfig(id="nlp"),
        )
        with self.assertRaises(ValueError):
            await knot.process(
                pool=_StubPool(),
                query="SELECT 1",
                text_column="",
                target_column="label",
                embedding_provider=_StubProvider(),
            )

    async def test_rejects_wrong_provider_type(self) -> None:
        knot = NLPPipeline(
            pool=_StubPool(),
            query="SELECT 1",
            text_column="text",
            target_column="label",
            embedding_provider=_StubProvider(),
            _config=KnotConfig(id="nlp"),
        )
        with self.assertRaises(TypeError):
            await knot.process(
                pool=_StubPool(),
                query="SELECT 1",
                text_column="text",
                target_column="label",
                embedding_provider="bad",  # type: ignore[arg-type]
            )
