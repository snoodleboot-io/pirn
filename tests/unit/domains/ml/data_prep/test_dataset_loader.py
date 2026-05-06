"""Tests for :class:`DatasetLoader`."""

from __future__ import annotations
import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestDatasetLoaderHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_loads_metadata_from_pool_query(self) -> None:
        pool = RecordingDatabasePool(rows=[(1,), (2,), (3,)])
        with Tapestry() as t:
            DatasetLoader(
                name="customers",
                feature_names=("age", "income"),
                target_name="churned",
                pool=pool,
                query="SELECT id FROM customers",
                _config=KnotConfig(id="loader"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: MLDataset = result.outputs["loader"]
        assert isinstance(out, MLDataset)
        assert out.name == "customers"
        assert out.feature_names == ("age", "income")
        assert out.target_name == "churned"
        assert out.row_count == 3
        assert pool.queries == [("SELECT id FROM customers", None)]


class TestDatasetLoaderProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DatasetLoader:
        with Tapestry():
            loader = DatasetLoader.__new__(DatasetLoader)
            object.__setattr__(loader, "_config", KnotConfig(id="x"))
        return loader

    async def test_rejects_missing_inputs(self) -> None:
        loader = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await loader.process(
                name="customers",
                feature_names=("a",),
            )

    async def test_rejects_pool_query_and_parquet_together(self) -> None:
        loader = self._make_knot()
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await loader.process(
                name="customers",
                feature_names=("a",),
                pool=pool,
                query="SELECT 1",
                parquet_path="/tmp/out.parquet",
            )

    async def test_rejects_empty_feature_names(self) -> None:
        loader = self._make_knot()
        pool = RecordingDatabasePool()
        with pytest.raises(ValueError, match="feature_names"):
            await loader.process(
                name="customers",
                feature_names=(),
                pool=pool,
                query="SELECT 1",
            )
