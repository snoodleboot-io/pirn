"""Tests for :class:`DataBatchToDuckdb`."""

from __future__ import annotations
import unittest

import duckdb

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.duckdb.bridges.data_batch_to_duckdb import (
    DataBatchToDuckdb,
)
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch
from pirn.tapestry import Tapestry


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
        connection = duckdb.connect(database=":memory:")
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToDuckdb(
                batch=batch,
                connection=connection,
                _config=KnotConfig(id="duck"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["duck"]
        assert out.connection is connection
