"""Unit tests for :class:`ImageEmbeddingExtractor` (specializations/feature_engineering)."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider
from pirn.domains.ml.specializations.feature_engineering.image_embedding_extractor import (
    ImageEmbeddingExtractor,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry


class _StubEncoder(ImageEncoderProvider):
    async def encode(self, images, *, model=None):
        return [[0.1] for _ in images]

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
            ImageEmbeddingExtractor(
                split=_KnotStub(_config=KnotConfig(id="s")),
                image_column="img",
                image_encoder=_StubEncoder(),
                _config=KnotConfig(id="iee"),
            )
        self.assertIsNotNone(t._store.get("iee"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> ImageEmbeddingExtractor:
        k = ImageEmbeddingExtractor.__new__(ImageEmbeddingExtractor)
        object.__setattr__(k, "_config", KnotConfig(id="iee"))
        return k

    def _make_split(self) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("img",), row_count=5)
        return SplitManifest(train=ds, test=ds)

    async def test_rejects_empty_image_column(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                image_column="",
                image_encoder=_StubEncoder(),
            )

    async def test_rejects_wrong_encoder_type(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                image_column="img",
                image_encoder="bad",  # type: ignore[arg-type]
            )
