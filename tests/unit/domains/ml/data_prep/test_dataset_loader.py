"""Tests for :class:`DatasetLoader`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestDatasetLoaderHappyPath:
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


class TestDatasetLoaderConstruction:
    def test_rejects_missing_inputs(self) -> None:
        with Tapestry():
            with pytest.raises(
                ValueError, match="exactly one of"
            ):
                DatasetLoader(
                    name="customers",
                    feature_names=("a",),
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_pool_query_and_parquet_together(self) -> None:
        pool = RecordingDatabasePool()
        with Tapestry():
            with pytest.raises(ValueError, match="exactly one of"):
                DatasetLoader(
                    name="customers",
                    feature_names=("a",),
                    pool=pool,
                    query="SELECT 1",
                    parquet_path="/tmp/out.parquet",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_feature_names(self) -> None:
        pool = RecordingDatabasePool()
        with Tapestry():
            with pytest.raises(ValueError, match="feature_names"):
                DatasetLoader(
                    name="customers",
                    feature_names=(),
                    pool=pool,
                    query="SELECT 1",
                    _config=KnotConfig(id="bad"),
                )
