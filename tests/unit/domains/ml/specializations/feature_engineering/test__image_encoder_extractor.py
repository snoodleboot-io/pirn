"""Unit tests for :class:`_ImageEncoderExtractor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider
from pirn.domains.ml.specializations.feature_engineering._image_encoder_extractor import (
    _ImageEncoderExtractor,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


class _StubEncoder(ImageEncoderProvider):
    async def encode(self, images, *, model=None):
        return [[0.5] for _ in images]

    async def close(self) -> None:
        pass


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("img",), row_count=5)
        return DataSplit(train=ds, test=ds)


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_image_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                _ImageEncoderExtractor(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    image_column="",
                    image_encoder=_StubEncoder(),
                    _config=KnotConfig(id="iee"),
                )

    def test_rejects_wrong_encoder_type(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                _ImageEncoderExtractor(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    image_column="img",
                    image_encoder="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="iee"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_embedding_feature(self) -> None:
        with Tapestry() as t:
            src = _SplitSource(_config=KnotConfig(id="src"))
            _ImageEncoderExtractor(
                split=src,
                image_column="img",
                image_encoder=_StubEncoder(),
                _config=KnotConfig(id="iee"),
            )
        result = await t.run(RunRequest())
        split = result.outputs["iee"]
        self.assertIn("img_embedding", split.train.feature_names)
