"""Unit tests for :class:`ImageEmbeddingExtractor` (domains/ml/features/)."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.image_embedding_extractor import ImageEmbeddingExtractor
from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


class _StubEncoder(ImageEncoderProvider):
    async def encode(self, images, *, model=None):
        return [[0.1, 0.2] for _ in images]

    async def close(self) -> None:
        pass


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("img_col", "x"), row_count=10)
        return DataSplit(train=ds, test=ds)


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_image_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                src = _SplitSource(_config=KnotConfig(id="src"))
                ImageEmbeddingExtractor(
                    split=src,
                    image_column="",
                    image_encoder=_StubEncoder(),
                    _config=KnotConfig(id="ext"),
                )

    def test_rejects_wrong_encoder_type(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                src = _SplitSource(_config=KnotConfig(id="src"))
                ImageEmbeddingExtractor(
                    split=src,
                    image_column="img",
                    image_encoder="not-an-encoder",  # type: ignore[arg-type]
                    _config=KnotConfig(id="ext"),
                )


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
        self.assertIsInstance(split, DataSplit)
        self.assertIn("img_col_embedding", split.train.feature_names)
