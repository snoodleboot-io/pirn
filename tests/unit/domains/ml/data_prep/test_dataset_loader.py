"""Tests for :class:`DatasetLoader`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.dataset_payload import DatasetPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestDatasetLoaderHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_loads_metadata_from_pool_query(self) -> None:
        rows = [
            {"age": 25.0, "income": 50000.0, "churned": 0.0},
            {"age": 30.0, "income": 60000.0, "churned": 1.0},
            {"age": 45.0, "income": 80000.0, "churned": 0.0},
        ]
        pool = RecordingDatabasePool(rows=rows)
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
        out: DatasetPayload = result.outputs["loader"]
        assert isinstance(out, DatasetPayload)
        assert isinstance(out.manifest, DatasetManifest)
        assert out.manifest.name == "customers"
        assert out.manifest.feature_names == ("age", "income")
        assert out.manifest.target_name == "churned"
        assert out.manifest.row_count == 3
        assert out.features.feature_matrix.shape == (3, 2)
        assert out.features.target_vector is not None
        assert out.features.target_vector.shape == (3,)
        assert pool.queries == [("SELECT id FROM customers", None)]


class TestDatasetLoaderProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DatasetLoader:
        with Tapestry():
            loader = DatasetLoader.__new__(DatasetLoader)
            object.__setattr__(loader, "_config", KnotConfig(id="x"))
        return loader

    async def test_rejects_missing_inputs(self) -> None:
        with Tapestry() as t:
            DatasetLoader(
                name="customers",
                feature_names=("a",),
                _config=KnotConfig(id="loader"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

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
