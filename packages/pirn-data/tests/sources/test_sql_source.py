"""Tests for :class:`SqlSource`."""

from __future__ import annotations

import unittest
from collections import namedtuple

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_data.sources.sql_source import SqlSource


class TestSqlSource(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = SqlitePool(SqliteConfig(database=":memory:"))
        await self.pool.execute("CREATE TABLE t (id INTEGER, name TEXT)")
        await self.pool.execute_many("INSERT INTO t (id, name) VALUES (?, ?)", [(1, "a"), (2, "b")])

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self) -> SqlSource:
        with Tapestry():
            return SqlSource(pool=self.pool, query="SELECT 1", _config=KnotConfig(id="sql"))

    async def test_positional_rows_are_keyed_by_position_as_strings(self) -> None:
        batch = await self._make_knot().process(
            pool=self.pool, query="SELECT id, name FROM t ORDER BY id"
        )
        assert batch.rows == ({"0": 1, "1": "a"}, {"0": 2, "1": "b"})
        assert batch.source_uri == "sql://SqlitePool"

    async def test_row_shapes_normalise_to_str_keyed_dicts(self) -> None:
        pair = namedtuple("pair", ["id", "name"])
        assert SqlSource._normalise_row({"id": 1}) == {"id": 1}
        assert SqlSource._normalise_row(pair(1, "a")) == {"id": 1, "name": "a"}
        assert SqlSource._normalise_row((1, "a")) == {"0": 1, "1": "a"}

    async def test_rejects_empty_query(self) -> None:
        with self.assertRaisesRegex(ValueError, "query"):
            await self._make_knot().process(pool=self.pool, query="")
