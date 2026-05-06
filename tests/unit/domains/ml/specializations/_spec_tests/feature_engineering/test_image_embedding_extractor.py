"""Tests for :class:`ImageEmbeddingExtractor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.image_embedding_extractor import (
    ImageEmbeddingExtractor,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_image_encoder_provider import (
    RecordingImageEncoderProvider,
)


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train", feature_names=("img",), target_name="y", row_count=80
    )
    test = MLDataset(
        name="d:test", feature_names=("img",), target_name="y", row_count=20
    )
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> DataSplit:
        train = MLDataset(
            name="d:train", feature_names=("img",), target_name="y", row_count=80
        )
        test = MLDataset(
            name="d:test", feature_names=("img",), target_name="y", row_count=20
        )
        return DataSplit(train=train, test=test)

    async def test_rejects_empty_image_column(self) -> None:
        with Tapestry():
            k = ImageEmbeddingExtractor.__new__(ImageEmbeddingExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                image_column="",
                image_encoder=RecordingImageEncoderProvider(),
            )

    async def test_rejects_non_encoder(self) -> None:
        with Tapestry():
            k = ImageEmbeddingExtractor.__new__(ImageEmbeddingExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                image_column="img",
                image_encoder="not-an-encoder",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_appends_image_embedding_feature(self) -> None:
        encoder = RecordingImageEncoderProvider()
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            ImageEmbeddingExtractor(
                split=split,
                image_column="img",
                image_encoder=encoder,
                _config=KnotConfig(id="emb"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["emb"]
        assert isinstance(out, DataSplit)
        assert "img_embedding" in out.train.feature_names
        assert "img_embedding" in out.test.feature_names
        assert encoder.calls
