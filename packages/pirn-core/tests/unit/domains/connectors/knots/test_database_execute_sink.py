"""Tests for :class:`DatabaseExecuteSink` calling process() directly."""

from __future__ import annotations

import unittest

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.connectors.knots.database_connection_pool_knot import DatabaseConnectionPoolKnot
from pirn.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.core.knot_config import KnotConfig


class TestDatabaseExecuteSink(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = SqlitePool(SqliteConfig(database=":memory:"))
        await self.pool.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, label TEXT)")
        pool_knot = DatabaseConnectionPoolKnot(pool=self.pool, _config=KnotConfig(id="pool"))
        self.sink = DatabaseExecuteSink(
            pool=pool_knot,
            query="SELECT 1",
            rows=pool_knot,  # dummy knot for wiring; process() called directly
            _config=KnotConfig(id="sink"),
        )

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_executes_one_query_per_row(self) -> None:
        rows = [(1, "alpha"), (2, "beta"), (3, "gamma")]
        count = await self.sink.process(
            pool=self.pool,
            query="INSERT INTO items (id, label) VALUES (?, ?)",
            rows=rows,
        )
        assert count == 3
        saved = await self.pool.fetch_all("SELECT id, label FROM items ORDER BY id")
        assert saved == [(1, "alpha"), (2, "beta"), (3, "gamma")]

    async def test_returns_row_count(self) -> None:
        count = await self.sink.process(
            pool=self.pool,
            query="INSERT INTO items (id, label) VALUES (?, ?)",
            rows=[(10, "x"), (11, "y")],
        )
        assert count == 2

    async def test_rejects_str_as_rows(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            await self.sink.process(
                pool=self.pool,
                query="INSERT INTO items VALUES (?, ?)",
                rows="not a list of tuples",  # type: ignore[arg-type]
            )
        assert "iterable of parameter tuples" in str(ctx.exception)

    async def test_rejects_bytes_as_rows(self) -> None:
        with self.assertRaises(TypeError):
            await self.sink.process(
                pool=self.pool,
                query="INSERT INTO items VALUES (?, ?)",
                rows=b"bytes",  # type: ignore[arg-type]
            )

    async def test_rejects_non_pool(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            await self.sink.process(
                pool=object(),  # type: ignore[arg-type]
                query="INSERT INTO items VALUES (?, ?)",
                rows=[],
            )
        assert "DatabaseConnectionPool" in str(ctx.exception)

    async def test_rejects_empty_query(self) -> None:
        with self.assertRaises(ValueError):
            await self.sink.process(
                pool=self.pool,
                query="",
                rows=[],
            )


class TestDatabaseConnectionPoolKnot(unittest.IsolatedAsyncioTestCase):
    async def test_returns_pool_unchanged(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        try:
            knot = DatabaseConnectionPoolKnot(pool=pool, _config=KnotConfig(id="pool"))
            result = await knot.process(pool=pool)
            assert result is pool
        finally:
            await pool.close()
