"""Tests for :class:`DatabaseExecuteSink` against an in-memory SqlitePool."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.tapestry import Tapestry


@knot
async def emit_rows() -> list[tuple[int, str]]:
    return [(1, "alpha"), (2, "beta"), (3, "gamma")]


class TestDatabaseExecuteSink(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = SqlitePool(SqliteConfig(database=":memory:"))
        await self.pool.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, label TEXT)")

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_executes_one_query_per_row(self) -> None:
        with Tapestry() as t:
            rows = emit_rows(_config=KnotConfig(id="rows"))
            DatabaseExecuteSink(
                pool=self.pool,
                query="INSERT INTO items (id, label) VALUES (?, ?)",
                rows=rows,
                _config=KnotConfig(id="sink"),
            )

        result = await t.run(RunRequest())
        assert result.succeeded

        saved = await self.pool.fetch_all("SELECT id, label FROM items ORDER BY id")
        assert saved == [(1, "alpha"), (2, "beta"), (3, "gamma")]

    async def test_rejects_str_or_bytes_as_rows(self) -> None:
        @knot
        async def emit_string() -> str:
            return "not a list of tuples"

        with Tapestry() as t:
            s = emit_string(_config=KnotConfig(id="bad"))
            DatabaseExecuteSink(
                pool=self.pool,
                query="INSERT INTO items VALUES (?, ?)",
                rows=s,
                _config=KnotConfig(id="sink", validate_io=False),
            )

        result = await t.run(RunRequest())
        assert not result.succeeded
        assert any(
            "iterable of parameter tuples" in (exc.message or "")
            for exc in result.exceptions
        )

    def test_construct_rejects_non_pool(self) -> None:
        @knot
        async def empty_rows() -> list[tuple]:
            return []

        with Tapestry():
            rows = empty_rows(_config=KnotConfig(id="rows"))
            with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
                DatabaseExecuteSink(
                    pool=object(),  # type: ignore[arg-type]
                    query="INSERT INTO t VALUES (?)",
                    rows=rows,
                    _config=KnotConfig(id="sink"),
                )
