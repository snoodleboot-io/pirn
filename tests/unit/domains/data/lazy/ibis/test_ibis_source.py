"""Tests for :class:`IbisSource`."""

from __future__ import annotations

import unittest

import ibis

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ibis.ibis_connection import IbisConnection
from pirn.domains.data.lazy.ibis.ibis_connection_knot import IbisConnectionKnot
from pirn.domains.data.lazy.ibis.ibis_source import IbisSource
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.tapestry import Tapestry


class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    async def test_ibis_source_emits_deferred_expression(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "users",
            {"id": [1, 2, 3], "name": ["alice", "bob", "carol"]},
        )
        with Tapestry() as t:
            conn_knot = IbisConnectionKnot(
                backend=con,
                _config=KnotConfig(id="conn"),
            )
            IbisSource(
                connection=conn_knot,
                table="users",
                backend_name="duckdb",
                _config=KnotConfig(id="users"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: IbisTable = result.outputs["users"]
        assert out.backend_name == "duckdb"
        assert set(out.column_names) == {"id", "name"}

    async def test_process_rejects_missing_connection_value(self) -> None:
        """process() rejects an empty table name."""
        con = ibis.duckdb.connect()
        con.create_table(
            "users",
            {"id": [1, 2, 3], "name": ["alice", "bob", "carol"]},
        )
        wrapped = IbisConnection(backend=con)
        src = object.__new__(IbisSource)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await IbisSource.process(src, connection=wrapped, table="")

    async def test_process_rejects_empty_table_name(self) -> None:
        con = ibis.duckdb.connect()
        wrapped = IbisConnection(backend=con)
        src = object.__new__(IbisSource)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await IbisSource.process(src, connection=wrapped, table="")
