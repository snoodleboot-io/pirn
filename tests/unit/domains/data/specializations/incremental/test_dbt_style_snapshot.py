"""Tests for :class:`DbtStyleSnapshot`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.incremental.dbt_style_snapshot import DbtStyleSnapshot
from pirn.tapestry import Tapestry

_SOURCE_QUERY = "SELECT id, status FROM orders ORDER BY id"
_TARGET_TABLE = "orders_snapshot"
_KEY_COLS = ("id",)
_TRACKED_COLS = ("status",)

_TARGET_DDL = (
    "CREATE TABLE orders_snapshot ("
    "  id INTEGER NOT NULL,"
    "  status TEXT NOT NULL,"
    "  dbt_valid_from TEXT NOT NULL,"
    "  dbt_valid_to TEXT,"
    "  dbt_is_current INTEGER NOT NULL,"
    "  dbt_scd_id TEXT NOT NULL"
    ")"
)


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, status TEXT NOT NULL)"
    )
    await src.execute_many(
        "INSERT INTO orders (id, status) VALUES (?, ?)",
        [(1, "pending"), (2, "shipped")],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(_TARGET_DDL)
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> DbtStyleSnapshot:
    return DbtStyleSnapshot(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        key_columns=_KEY_COLS,
        tracked_columns=_TRACKED_COLS,
        _config=KnotConfig(id="snap"),
    )


class TestDbtStyleSnapshot(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_first_run_inserts_all_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT id FROM orders_snapshot WHERE dbt_is_current = 1 ORDER BY id"
        )
        assert [r[0] for r in rows] == [1, 2]

    async def test_unchanged_rows_not_duplicated(self) -> None:
        for _ in range(2):
            with Tapestry() as t:
                _make_knot(self.src, self.tgt)
            await t.run(RunRequest())
        rows = await self.tgt.fetch_all(
            "SELECT COUNT(*) FROM orders_snapshot WHERE id = 1 AND dbt_is_current = 1"
        )
        assert rows[0][0] == 1

    async def test_changed_row_closes_old_and_inserts_new(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        await t.run(RunRequest())
        await self.src.execute("UPDATE orders SET status = ? WHERE id = ?", ("delivered", 1))
        with Tapestry() as t2:
            _make_knot(self.src, self.tgt)
        result = await t2.run(RunRequest())
        assert result.succeeded
        current = await self.tgt.fetch_all(
            "SELECT status FROM orders_snapshot WHERE id = 1 AND dbt_is_current = 1"
        )
        assert current[0][0] == "delivered"
        closed = await self.tgt.fetch_all(
            "SELECT COUNT(*) FROM orders_snapshot WHERE id = 1 AND dbt_is_current = 0"
        )
        assert closed[0][0] == 1

    async def test_result_tracks_inserted_and_closed(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["rows_inserted"] == 2
        assert out["rows_closed"] == 0


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
            DbtStyleSnapshot(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                key_columns=_KEY_COLS,
                tracked_columns=_TRACKED_COLS,
                _config=KnotConfig(id="snap"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["snap"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> DbtStyleSnapshot:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "key_columns": _KEY_COLS,
            "tracked_columns": _TRACKED_COLS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return DbtStyleSnapshot(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: DbtStyleSnapshot, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "key_columns": _KEY_COLS,
            "tracked_columns": _TRACKED_COLS,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_overlapping_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "overlap"):
            await self._call(k, key_columns=("id", "status"), tracked_columns=("status",))

    async def test_rejects_empty_source_query(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_query"):
            await self._call(k, source_query="")
