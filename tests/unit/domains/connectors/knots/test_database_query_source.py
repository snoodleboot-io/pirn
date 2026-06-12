"""Tests for :class:`DatabaseQuerySource` calling process() directly."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.connectors.knots.database_connection_pool_knot import DatabaseConnectionPoolKnot
from pirn.connectors.knots.database_query_source import DatabaseQuerySource


class TestDatabaseQuerySource(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = SqlitePool(SqliteConfig(database=":memory:"))
        await self.pool.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        await self.pool.execute("INSERT INTO users (id, name) VALUES (?, ?)", (1, "alice"))
        await self.pool.execute("INSERT INTO users (id, name) VALUES (?, ?)", (2, "bob"))
        pool_knot = DatabaseConnectionPoolKnot(pool=self.pool, _config=KnotConfig(id="pool"))
        self.source = DatabaseQuerySource(
            pool=pool_knot,
            query="SELECT 1",
            _config=KnotConfig(id="source"),
        )

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_query_returns_rows(self) -> None:
        rows = await self.source.process(
            pool=self.pool,
            query="SELECT id, name FROM users ORDER BY id",
        )
        assert rows == [(1, "alice"), (2, "bob")]

    async def test_query_with_parameters(self) -> None:
        rows = await self.source.process(
            pool=self.pool,
            query="SELECT name FROM users WHERE id = ?",
            parameters=(2,),
        )
        assert rows == [("bob",)]

    async def test_no_parameters_defaults_to_empty(self) -> None:
        rows = await self.source.process(
            pool=self.pool,
            query="SELECT id FROM users ORDER BY id",
        )
        assert rows == [(1,), (2,)]

    async def test_rejects_non_pool(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            await self.source.process(
                pool=object(),  # type: ignore[arg-type]
                query="SELECT 1",
            )
        assert "DatabaseConnectionPool" in str(ctx.exception)

    async def test_rejects_empty_query(self) -> None:
        with self.assertRaises(ValueError):
            await self.source.process(pool=self.pool, query="")
