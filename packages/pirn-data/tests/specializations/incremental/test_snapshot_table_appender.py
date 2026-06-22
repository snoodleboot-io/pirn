"""Tests for :class:`SnapshotTableAppender`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.incremental.snapshot_table_appender import (
    SnapshotTableAppender,
)

_SOURCE_QUERY = "SELECT id, name FROM products ORDER BY id"
_TARGET_TABLE = "products_snapshot"
_SRC_COLS = ("id", "name")


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )
    await src.execute_many(
        "INSERT INTO products (id, name) VALUES (?, ?)",
        [(1, "Alpha"), (2, "Beta")],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
        "CREATE TABLE products_snapshot (id INTEGER, name TEXT, _snapshot_date TEXT NOT NULL)"
    )
    return src, tgt


class TestSnapshotTableAppender(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_appends_all_source_rows_with_snapshot_date(self) -> None:
        with Tapestry() as t:
            SnapshotTableAppender(
                source_pool=self.src,
                source_query=_SOURCE_QUERY,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                source_columns=_SRC_COLS,
                _config=KnotConfig(id="snap"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all("SELECT id, name FROM products_snapshot ORDER BY id")
        assert rows == [(1, "Alpha"), (2, "Beta")]
        date_rows = await self.tgt.fetch_all(
            "SELECT DISTINCT _snapshot_date FROM products_snapshot"
        )
        assert len(date_rows) == 1
        assert date_rows[0][0] is not None

    async def test_second_run_appends_another_snapshot(self) -> None:
        for _ in range(2):
            with Tapestry() as t:
                SnapshotTableAppender(
                    source_pool=self.src,
                    source_query=_SOURCE_QUERY,
                    target_pool=self.tgt,
                    target_table=_TARGET_TABLE,
                    source_columns=_SRC_COLS,
                    _config=KnotConfig(id="snap"),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await self.tgt.fetch_all("SELECT id FROM products_snapshot ORDER BY id")
        assert len(rows) == 4

    async def test_result_contains_rows_appended(self) -> None:
        with Tapestry() as t:
            k = SnapshotTableAppender(
                source_pool=self.src,
                source_query=_SOURCE_QUERY,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                source_columns=_SRC_COLS,
                _config=KnotConfig(id="snap"),
            )
        result = await t.run(RunRequest())
        assert result.outputs[k.config.id]["rows_appended"] == 2


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_source_query_from_upstream_knot(self) -> None:
        @knot
        async def emit_query() -> str:
            return _SOURCE_QUERY

        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            SnapshotTableAppender(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                source_columns=_SRC_COLS,
                _config=KnotConfig(id="snap"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["snap"]["rows_appended"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> SnapshotTableAppender:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "source_columns": _SRC_COLS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return SnapshotTableAppender(**defaults, _config=KnotConfig(id="snap"))

    async def _call(self, k: SnapshotTableAppender, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "source_columns": _SRC_COLS,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_non_pool_target(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, target_pool="bad")

    async def test_rejects_empty_source_query(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_query"):
            await self._call(k, source_query="")

    async def test_rejects_invalid_table_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, target_table="bad table name")
