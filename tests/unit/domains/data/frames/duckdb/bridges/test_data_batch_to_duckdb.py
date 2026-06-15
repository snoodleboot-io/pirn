"""Tests for :class:`DataBatchToDuckdb`."""

from __future__ import annotations

import unittest

try:
    import duckdb
except ImportError as _e:
    raise unittest.SkipTest("duckdb not installed") from _e

import duckdb
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.data_batch import DataBatch
from pirn_data.frames.duckdb.bridges.data_batch_to_duckdb import (
    DataBatchToDuckdb,
)
from pirn_data.frames.duckdb.duckdb_connection import DuckDBConnection
from pirn_data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch


@knot
async def emit_users() -> DataBatch:
    rows = (
        {"id": 1, "name": "alice"},
        {"id": 2, "name": "bob"},
    )
    return DataBatch(rows=rows, source_uri="memory://users")


@knot
async def emit_empty() -> DataBatch:
    return DataBatch()


def _make_batch() -> DataBatch:
    return DataBatch(
        rows=({"id": 1, "name": "alice"},),
        source_uri="memory://test",
    )


class TestDataBatchToDuckdb(unittest.IsolatedAsyncioTestCase):
    async def test_constructs_relation_from_rows(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToDuckdb(batch=batch, _config=KnotConfig(id="duck"))
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["duck"]
        assert set(out.column_names) == {"id", "name"}
        rows = out.relation.fetchall()
        assert len(rows) == 2

    async def test_propagates_metadata(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToDuckdb(batch=batch, _config=KnotConfig(id="duck"))
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["duck"]
        assert out.source_uri == "memory://users"

    async def test_empty_batch_yields_empty_relation(self) -> None:
        with Tapestry() as t:
            batch = emit_empty(_config=KnotConfig(id="empty"))
            DataBatchToDuckdb(batch=batch, _config=KnotConfig(id="duck"))
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["duck"]
        assert out.relation.fetchall() == []

    async def test_uses_supplied_connection(self) -> None:
        raw_conn = duckdb.connect(database=":memory:")
        connection = DuckDBConnection(raw_conn)
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToDuckdb(
                batch=batch,
                connection=connection,
                _config=KnotConfig(id="duck"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["duck"]
        assert out.connection is raw_conn


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_connection_from_upstream_knot(self) -> None:
        @knot
        async def emit_connection() -> DuckDBConnection:
            return DuckDBConnection(duckdb.connect(database=":memory:"))

        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            conn_knot = emit_connection(_config=KnotConfig(id="conn"))
            DataBatchToDuckdb(
                batch=batch,
                connection=conn_knot,
                _config=KnotConfig(id="duck"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["duck"]
        assert set(out.column_names) == {"id", "name"}


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: object) -> DataBatchToDuckdb:
        @knot
        async def upstream() -> DataBatch:
            return _make_batch()

        with Tapestry():
            batch = upstream(_config=KnotConfig(id="up"))
            return DataBatchToDuckdb(batch=batch, _config=KnotConfig(id="b"), **kwargs)

    async def test_rejects_non_connection_object(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "DuckDBConnection"):
            await k.process(batch=_make_batch(), connection="not-a-connection")
