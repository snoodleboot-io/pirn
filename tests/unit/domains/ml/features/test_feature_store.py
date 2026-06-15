"""Tests for :class:`FeatureStore`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.feature_store import FeatureStore
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry

from tests.unit.domains.ml._stubs.recording_feature_store_provider import (
    RecordingFeatureStoreProvider,
)


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=10)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=5)
    return SplitManifest(train=train, test=test)


class TestFeatureStoreHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_writes_partition_metadata(self) -> None:
        provider = RecordingFeatureStoreProvider()
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            FeatureStore(
                split=split,
                provider=provider,
                _config=KnotConfig(id="store"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["store"] == 2  # train + test
        partitions = [row["partition"] for row in provider.written]
        assert partitions == ["train", "test"]


class TestFeatureStoreProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_provider(self) -> None:
        store = FeatureStore.__new__(FeatureStore)
        object.__setattr__(store, "_config", KnotConfig(id="x"))
        train = DatasetManifest(name="d:train", feature_names=("a",), row_count=10)
        test = DatasetManifest(name="d:test", feature_names=("a",), row_count=5)
        split = SplitManifest(train=train, test=test)
        with self.assertRaisesRegex(TypeError, "FeatureStoreProvider"):
            await store.process(
                split=split,
                provider="not a provider",  # type: ignore[arg-type]
            )
