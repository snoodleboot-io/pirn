"""Tests for :class:`FeatureStore`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.feature_store import FeatureStore
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_feature_store_provider import (
    RecordingFeatureStoreProvider,
)


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a",), row_count=10)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=5)
    return DataSplit(train=train, test=test)


class TestFeatureStoreHappyPath:
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


class TestFeatureStoreConstruction:
    def test_rejects_non_provider(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(TypeError, match="FeatureStoreProvider"):
                FeatureStore(
                    split=split,
                    provider="not a provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )
