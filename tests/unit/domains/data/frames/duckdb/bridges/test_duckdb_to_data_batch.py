"""Tests for :class:`DuckdbToDataBatch`."""

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
from pirn_data.frames.duckdb.bridges.duckdb_to_data_batch import (
    DuckdbToDataBatch,
)
from pirn_data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch


@knot
async def emit_duckdb_batch() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    connection.execute(
        "CREATE TABLE t AS "
        "SELECT * FROM (VALUES (1, 'a'), (2, 'b'), (3, 'c')) AS v(id, name)"
    )
    relation = connection.table("t")
    return DuckdbDataBatch(
        relation=relation, connection=connection, source_uri="memory://x"
    )


class TestDuckdbToDataBatch(unittest.IsolatedAsyncioTestCase):
    async def test_materialises_rows_as_dicts(self) -> None:
        with Tapestry() as t:
            batch = emit_duckdb_batch(_config=KnotConfig(id="duck"))
            DuckdbToDataBatch(batch=batch, _config=KnotConfig(id="dict"))
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dict"]
        assert out.row_count == 3
        assert out.rows == (
            {"id": 1, "name": "a"},
            {"id": 2, "name": "b"},
            {"id": 3, "name": "c"},
        )

    async def test_propagates_metadata(self) -> None:
        with Tapestry() as t:
            batch = emit_duckdb_batch(_config=KnotConfig(id="duck"))
            DuckdbToDataBatch(batch=batch, _config=KnotConfig(id="dict"))
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dict"]
        assert out.source_uri == "memory://x"
