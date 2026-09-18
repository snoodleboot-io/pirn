"""Tests for :class:`DatasetLoader`."""

from __future__ import annotations

import unittest
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.lakehouse.lakehouse_table import LakehouseTable

from pirn_ml.data_prep.dataset_loader import DatasetLoader
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.dataset_payload import DatasetPayload
from tests._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class _StubLakehouseTable(LakehouseTable):
    """A lakehouse table reference that is never scanned."""


class _FailingDatabasePool(RecordingDatabasePool):
    """A pool whose query fails at run time."""

    async def fetch_all(self, query: str, params: tuple[Any, ...] | None = None) -> list[Any]:
        self.queries.append((query, params))
        raise ConnectionError("warehouse connection refused")


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
        assert isinstance(out.metadata, DatasetManifest)
        assert out.metadata.name == "customers"
        assert out.metadata.feature_names == ("age", "income")
        assert out.metadata.target_name == "churned"
        assert out.metadata.row_count == 3
        assert out.data.feature_matrix.shape == (3, 2)
        assert out.data.target_vector is not None
        assert out.data.target_vector.shape == (3,)
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


class TestDatasetLoaderSourceFailuresSurface(unittest.IsolatedAsyncioTestCase):
    async def test_failing_source_fails_the_run_with_its_own_error(self) -> None:
        pool = _FailingDatabasePool()
        with Tapestry() as t:
            DatasetLoader(
                name="customers",
                feature_names=("age",),
                pool=pool,
                query="SELECT age FROM customers",
                _config=KnotConfig(id="loader"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
        assert pool.queries == [("SELECT age FROM customers", None)]
        messages = " ".join(record.message for record in result.exceptions)
        assert "warehouse connection refused" in messages
        assert "no source produced data" not in messages

    async def test_rejects_partially_configured_source(self) -> None:
        with Tapestry():
            loader = DatasetLoader.__new__(DatasetLoader)
            object.__setattr__(loader, "_config", KnotConfig(id="x"))
        with pytest.raises(
            ValueError, match=r"sql source is partially configured.*missing \['query'\]"
        ):
            await loader.process(
                name="customers", feature_names=("age",), pool=RecordingDatabasePool()
            )

    async def test_rejects_more_than_one_configured_source(self) -> None:
        with Tapestry():
            loader = DatasetLoader.__new__(DatasetLoader)
            object.__setattr__(loader, "_config", KnotConfig(id="x"))
        with pytest.raises(ValueError, match="configure exactly one source"):
            await loader.process(
                name="customers",
                feature_names=("age",),
                table=_StubLakehouseTable(),
                pool=RecordingDatabasePool(),
                query="SELECT age FROM customers",
            )
