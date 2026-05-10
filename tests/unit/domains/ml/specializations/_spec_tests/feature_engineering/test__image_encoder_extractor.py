"""Tests for :class:`_ImageEncoderExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.feature_engineering._image_encoder_extractor import (
    _ImageEncoderExtractor,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_image_encoder_provider import (
    RecordingImageEncoderProvider,
)


def _split_fixture() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("img",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("img",), row_count=20)
    return SplitManifest(train=train, test=test)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_image_column(self) -> None:
        with Tapestry():
            k = _ImageEncoderExtractor.__new__(_ImageEncoderExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                image_column="",
                image_encoder=RecordingImageEncoderProvider(),
            )

    async def test_rejects_non_provider(self) -> None:
        with Tapestry():
            k = _ImageEncoderExtractor.__new__(_ImageEncoderExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                image_column="img",
                image_encoder="not-a-provider",  # type: ignore[arg-type]
            )
