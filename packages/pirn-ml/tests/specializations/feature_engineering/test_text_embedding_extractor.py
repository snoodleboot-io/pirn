"""Unit tests for :class:`TextEmbeddingExtractor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_ml.ml_embedding_provider import MLEmbeddingProvider
from pirn_ml.specializations.feature_engineering.text_embedding_extractor import (
    TextEmbeddingExtractor,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


class _StubProvider(MLEmbeddingProvider):
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
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            TextEmbeddingExtractor(
                split=_KnotStub(_config=KnotConfig(id="s")),
                text_column="text",
                embedding_provider=_StubProvider(),
                _config=KnotConfig(id="tee"),
            )
        self.assertIsNotNone(t._store.get("tee"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> TextEmbeddingExtractor:
        k = TextEmbeddingExtractor.__new__(TextEmbeddingExtractor)
        object.__setattr__(k, "_config", KnotConfig(id="tee"))
        return k

    def _make_split(self) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("text",), row_count=5)
        return SplitManifest(train=ds, test=ds)

    async def test_rejects_empty_text_column(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                text_column="",
                embedding_provider=_StubProvider(),
            )

    async def test_rejects_wrong_provider_type(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                text_column="text",
                embedding_provider="bad",  # type: ignore[arg-type]
            )
