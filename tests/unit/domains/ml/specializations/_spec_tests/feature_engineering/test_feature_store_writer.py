"""Tests for :class:`FeatureStoreWriter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.feature_store_writer import (
    FeatureStoreWriter,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_feature_store_provider import (
    RecordingFeatureStoreProvider,
)


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train", feature_names=("a",), target_name="y", row_count=80
    )
    test = MLDataset(
        name="d:test", feature_names=("a",), target_name="y", row_count=20
    )
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.TestCase):
    def test_rejects_non_provider(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(TypeError, "FeatureStoreProvider"):
                FeatureStoreWriter(
                    split=split,
                    feature_store="not-a-store",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_non_knot_split(self) -> None:
        with Tapestry():
            store = RecordingFeatureStoreProvider()
            with self.assertRaisesRegex(TypeError, "split must be a Knot"):
                FeatureStoreWriter(
                    split="not-a-knot",  # type: ignore[arg-type]
                    feature_store=store,
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_writes_partition_metadata(self) -> None:
        store = RecordingFeatureStoreProvider()
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            FeatureStoreWriter(
                split=split,
                feature_store=store,
                _config=KnotConfig(id="fsw"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        written = result.outputs["fsw"]
        assert isinstance(written, int)
        assert written == 2  # train + test partitions
        assert len(store.written) == 2
