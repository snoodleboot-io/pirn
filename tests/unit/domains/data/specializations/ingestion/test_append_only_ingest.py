"""Tests for :class:`AppendOnlyIngest`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.ingestion.append_only_ingest import (
    AppendOnlyIngest,
)
from pirn.tapestry import Tapestry


class TestAppendOnlyIngest(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, payload TEXT)")
        await pool.execute_many(
            "INSERT INTO events (id, payload) VALUES (?, ?)",
            [(1, "a"), (2, "b"), (3, "c")],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, payload TEXT)")
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    async def test_appends_all_source_rows(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            AppendOnlyIngest(
                source_pool=source_pool,
                source_query="SELECT id, payload FROM events ORDER BY id",
                target_pool=target_pool,
                insert_query="INSERT INTO events (id, payload) VALUES (?, ?)",
                _config=KnotConfig(id="append"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all("SELECT id, payload FROM events ORDER BY id")
        assert rows == [(1, "a"), (2, "b"), (3, "c")]

    async def test_preserves_existing_target_rows(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        # Seed the target.
        await target_pool.execute_many(
            "INSERT INTO events (id, payload) VALUES (?, ?)",
            [(0, "preexisting")],
        )
        with Tapestry() as t:
            AppendOnlyIngest(
                source_pool=source_pool,
                source_query="SELECT id, payload FROM events ORDER BY id",
                target_pool=target_pool,
                insert_query="INSERT INTO events (id, payload) VALUES (?, ?)",
                _config=KnotConfig(id="append"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT id FROM events ORDER BY id"
        )
        # Pre-existing row plus 3 new rows.
        assert rows == [(0,), (1,), (2,), (3,)]
