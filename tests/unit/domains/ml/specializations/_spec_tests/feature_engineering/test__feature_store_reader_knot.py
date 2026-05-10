"""Tests for :class:`_FeatureStoreReaderKnot`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.feature_engineering._feature_store_reader_knot import (
    _FeatureStoreReaderKnot,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_feature_store_provider import (
    RecordingFeatureStoreProvider,
)


def _split_fixture() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_provider(self) -> None:
        with Tapestry():
            k = _FeatureStoreReaderKnot.__new__(_FeatureStoreReaderKnot)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                feature_store="not-a-store",  # type: ignore[arg-type]
                entity_keys=("id",),
                feature_names=("feat",),
            )

    async def test_rejects_empty_entity_keys(self) -> None:
        with Tapestry():
            k = _FeatureStoreReaderKnot.__new__(_FeatureStoreReaderKnot)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                feature_store=RecordingFeatureStoreProvider(),
                entity_keys=(),
                feature_names=("feat",),
            )

    async def test_rejects_empty_feature_names(self) -> None:
        with Tapestry():
            k = _FeatureStoreReaderKnot.__new__(_FeatureStoreReaderKnot)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                feature_store=RecordingFeatureStoreProvider(),
                entity_keys=("id",),
                feature_names=(),
            )
