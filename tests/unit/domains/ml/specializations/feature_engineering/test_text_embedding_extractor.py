"""Unit tests for :class:`TextEmbeddingExtractor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.embedding_provider import EmbeddingProvider
from pirn.domains.ml.specializations.feature_engineering.text_embedding_extractor import (
    TextEmbeddingExtractor,
)
from pirn.tapestry import Tapestry


class _StubProvider(EmbeddingProvider):
    async def embed(self, texts, *, model=None):
        return [[0.1, 0.2] for _ in texts]

    async def close(self) -> None:
        pass


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_split(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                TextEmbeddingExtractor(
                    split="bad",  # type: ignore[arg-type]
                    text_column="text",
                    embedding_provider=_StubProvider(),
                    _config=KnotConfig(id="tee"),
                )

    def test_rejects_empty_text_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TextEmbeddingExtractor(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    text_column="",
                    embedding_provider=_StubProvider(),
                    _config=KnotConfig(id="tee"),
                )

    def test_rejects_wrong_provider_type(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                TextEmbeddingExtractor(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    text_column="text",
                    embedding_provider="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="tee"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            TextEmbeddingExtractor(
                split=_KnotStub(_config=KnotConfig(id="s")),
                text_column="text",
                embedding_provider=_StubProvider(),
                _config=KnotConfig(id="tee"),
            )
        self.assertIsNotNone(t._store.get("tee"))
