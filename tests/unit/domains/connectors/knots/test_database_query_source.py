"""Tests for :class:`DatabaseQuerySource` against an in-memory SqlitePool."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.connectors.knots.database_query_source import DatabaseQuerySource
from pirn.tapestry import Tapestry


class TestDatabaseQuerySource(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = SqlitePool(SqliteConfig(database=":memory:"))
        await self.pool.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        await self.pool.execute("INSERT INTO users (id, name) VALUES (?, ?)", (1, "alice"))
        await self.pool.execute("INSERT INTO users (id, name) VALUES (?, ?)", (2, "bob"))

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_query_returns_rows(self) -> None:
        with Tapestry() as t:
            DatabaseQuerySource(
                pool=self.pool,
                query="SELECT id, name FROM users ORDER BY id",
                _config=KnotConfig(id="users"),
            )

        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["users"] == [(1, "alice"), (2, "bob")]

    async def test_query_with_parameters(self) -> None:
        with Tapestry() as t:
            DatabaseQuerySource(
                pool=self.pool,
                query="SELECT name FROM users WHERE id = ?",
                parameters=(2,),
                _config=KnotConfig(id="user"),
            )

        result = await t.run(RunRequest())
        assert result.outputs["user"] == [("bob",)]

    def test_construct_rejects_non_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            DatabaseQuerySource(
                pool=object(),  # type: ignore[arg-type]
                query="SELECT 1",
                _config=KnotConfig(id="q"),
            )

    async def test_construct_rejects_empty_query(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            DatabaseQuerySource(
                pool=self.pool,
                query="",
                _config=KnotConfig(id="q"),
            )
