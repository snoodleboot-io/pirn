"""Tests for :class:`FeatureEngineeringImageEmbeddingExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.feature_engineering_image_embedding_extractor import (
    FeatureEngineeringImageEmbeddingExtractor,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_image_encoder_provider import (
    RecordingImageEncoderProvider,
)


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="d:train", feature_names=("img",), target_name="y", row_count=80
    )
    test = DatasetManifest(
        name="d:test", feature_names=("img",), target_name="y", row_count=20
    )
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> SplitManifest:
        train = DatasetManifest(
            name="d:train", feature_names=("img",), target_name="y", row_count=80
        )
        test = DatasetManifest(
            name="d:test", feature_names=("img",), target_name="y", row_count=20
        )
        return SplitManifest(train=train, test=test)

    async def test_rejects_empty_image_column(self) -> None:
        with Tapestry():
            k = FeatureEngineeringImageEmbeddingExtractor.__new__(FeatureEngineeringImageEmbeddingExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                image_column="",
                image_encoder=RecordingImageEncoderProvider(),
            )

    async def test_rejects_non_encoder(self) -> None:
        with Tapestry():
            k = FeatureEngineeringImageEmbeddingExtractor.__new__(FeatureEngineeringImageEmbeddingExtractor)
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
            FeatureEngineeringImageEmbeddingExtractor(
                split=split,
                image_column="img",
                image_encoder=encoder,
                _config=KnotConfig(id="emb"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["emb"]
        assert isinstance(out, SplitManifest)
        assert "img_embedding" in out.train.feature_names
        assert "img_embedding" in out.test.feature_names
        assert encoder.calls
