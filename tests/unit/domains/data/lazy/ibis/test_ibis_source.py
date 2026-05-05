"""Tests for :class:`IbisSource`."""

from __future__ import annotations
import unittest

import ibis

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
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
        duckdb_with_users = con
        with Tapestry() as t:
            IbisSource(
                connection=duckdb_with_users,
                table="users",
                backend_name="duckdb",
                _config=KnotConfig(id="users"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: IbisTable = result.outputs["users"]
        assert out.backend_name == "duckdb"
        assert set(out.column_names) == {"id", "name"}
    
    
    def test_construct_rejects_missing_connection(self) -> None:
        with self.assertRaisesRegex(TypeError, "connection is required"):
            IbisSource(
                connection=None,
                table="users",
                _config=KnotConfig(id="x"),
            )
    
    
    def test_construct_rejects_empty_table_name(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "users",
            {"id": [1, 2, 3], "name": ["alice", "bob", "carol"]},
        )
        duckdb_with_users = con
        with self.assertRaisesRegex(ValueError, "non-empty"):
            IbisSource(
                connection=duckdb_with_users,
                table="",
                _config=KnotConfig(id="x"),
            )
