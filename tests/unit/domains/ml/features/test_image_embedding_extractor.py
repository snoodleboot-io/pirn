"""Unit tests for :class:`ImageEmbeddingExtractor` (domains/ml/features/)."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.image_embedding_extractor import ImageEmbeddingExtractor
from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry


class _StubEncoder(ImageEncoderProvider):
    async def encode(self, images, *, model=None):
        return [[0.1, 0.2] for _ in images]

    async def close(self) -> None:
        pass


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("img_col", "x"), row_count=10)
        return SplitManifest(train=ds, test=ds)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("img_col", "x"), row_count=10)
        return SplitManifest(train=ds, test=ds)

    async def test_rejects_empty_image_column(self) -> None:
        with Tapestry():
            k = ImageEmbeddingExtractor.__new__(ImageEmbeddingExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="ext"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), image_column="", image_encoder=_StubEncoder())

    async def test_rejects_wrong_encoder_type(self) -> None:
        with Tapestry():
            k = ImageEmbeddingExtractor.__new__(ImageEmbeddingExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="ext"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), image_column="img", image_encoder="not-an-encoder")  # type: ignore[arg-type]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_embedding_feature(self) -> None:
        with Tapestry() as t:
            src = _SplitSource(_config=KnotConfig(id="src"))
            ImageEmbeddingExtractor(
                split=src,
                image_column="img_col",
                image_encoder=_StubEncoder(),
                _config=KnotConfig(id="ext"),
            )
        result = await t.run(RunRequest())
        split = result.outputs["ext"]
        self.assertIsInstance(split, SplitManifest)
        self.assertIn("img_col_embedding", split.train.feature_names)
