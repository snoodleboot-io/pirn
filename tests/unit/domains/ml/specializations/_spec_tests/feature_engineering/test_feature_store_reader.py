"""Tests for :class:`FeatureStoreReader`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.feature_store_reader import (
    FeatureStoreReader,
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
        name="d:train", feature_names=("entity_id",), target_name="y", row_count=80
    )
    test = MLDataset(
        name="d:test", feature_names=("entity_id",), target_name="y", row_count=20
    )
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> DataSplit:
        train = MLDataset(
            name="d:train", feature_names=("entity_id",), target_name="y", row_count=80
        )
        test = MLDataset(
            name="d:test", feature_names=("entity_id",), target_name="y", row_count=20
        )
        return DataSplit(train=train, test=test)

    async def test_rejects_empty_entity_keys(self) -> None:
        with Tapestry():
            k = FeatureStoreReader.__new__(FeatureStoreReader)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                feature_store=RecordingFeatureStoreProvider(),
                entity_keys=(),
                feature_names=("a",),
            )

    async def test_rejects_empty_feature_names(self) -> None:
        with Tapestry():
            k = FeatureStoreReader.__new__(FeatureStoreReader)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                feature_store=RecordingFeatureStoreProvider(),
                entity_keys=("entity_id",),
                feature_names=(),
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_joins_feature_names_and_probes_store(self) -> None:
        store = RecordingFeatureStoreProvider()
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            FeatureStoreReader(
                split=split,
                feature_store=store,
                entity_keys=("entity_id",),
                feature_names=("revenue", "tenure"),
                _config=KnotConfig(id="fsr"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["fsr"]
        assert isinstance(out, DataSplit)
        assert "revenue" in out.train.feature_names
        assert "tenure" in out.test.feature_names
        assert store.requested  # provider was probed
