"""Tests for :class:`ScdType7Hybrid`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.scd.scd_type_7_hybrid import ScdType7Hybrid

_SOURCE_QUERY = "SELECT id, region FROM customers ORDER BY id"
_TARGET_TABLE = "customers"
_KEY_COLS = ("id",)
_TRACKED_COLS = ("region",)
_CURRENT_COLS = {"region": "current_region"}


async def _make_src() -> SqlitePool:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, region TEXT)")
    await src.execute_many(
        "INSERT INTO customers (id, region) VALUES (?, ?)",
        [(1, "EU"), (2, "US")],
    )
    return src


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> ScdType7Hybrid:
    return ScdType7Hybrid(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        key_columns=_KEY_COLS,
        tracked_columns=_TRACKED_COLS,
        current_columns=_CURRENT_COLS,
        _config=KnotConfig(id="scd7h"),
    )


class TestScdType7Hybrid(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_src()
        self._tmp = tempfile.TemporaryDirectory()
        self.tgt = SqlitePool(
            SqliteConfig(database=str(Path(self._tmp.name) / "tgt.db"))
        )
        await self.tgt.execute(
            "CREATE TABLE customers ("
            "  id INTEGER NOT NULL,"
            "  region TEXT NOT NULL,"
            "  current_region TEXT,"
            "  valid_from TEXT NOT NULL,"
            "  valid_to TEXT,"
            "  is_current INTEGER NOT NULL"
            ")"
        )

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()
        self._tmp.cleanup()

    async def test_inserts_new_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT id, region, current_region, is_current FROM customers ORDER BY id"
        )
        assert rows == [(1, "EU", "EU", 1), (2, "US", "US", 1)]

    async def test_closes_old_and_inserts_new_on_change(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        await t.run(RunRequest())
        await self.src.execute("UPDATE customers SET region = ? WHERE id = ?", ("APAC", 1))
        with Tapestry() as t2:
            _make_knot(self.src, self.tgt)
        await t2.run(RunRequest())
        rows = await self.tgt.fetch_all(
            "SELECT region, is_current FROM customers WHERE id = 1 ORDER BY valid_from"
        )
        assert len(rows) == 2
        assert rows[0][1] == 0
        assert rows[1][0] == "APAC"
        assert rows[1][1] == 1

    async def test_backfills_current_mirror_on_all_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        await t.run(RunRequest())
        await self.src.execute("UPDATE customers SET region = ? WHERE id = ?", ("APAC", 1))
        with Tapestry() as t2:
            _make_knot(self.src, self.tgt)
        await t2.run(RunRequest())
        rows = await self.tgt.fetch_all(
            "SELECT current_region FROM customers WHERE id = 1"
        )
        for row in rows:
            assert row[0] == "APAC"

    async def test_result_counts(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["rows_inserted"] == 2
        assert out["rows_closed"] == 0


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_src()
        self._tmp = tempfile.TemporaryDirectory()
        self.tgt = SqlitePool(
            SqliteConfig(database=str(Path(self._tmp.name) / "tgt.db"))
        )
        await self.tgt.execute(
            "CREATE TABLE customers ("
            "  id INTEGER NOT NULL,"
            "  region TEXT NOT NULL,"
            "  current_region TEXT,"
            "  valid_from TEXT NOT NULL,"
            "  valid_to TEXT,"
            "  is_current INTEGER NOT NULL"
            ")"
        )

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()
        self._tmp.cleanup()

    async def test_source_query_from_upstream_knot(self) -> None:
        @knot
        async def emit_query() -> str:
            return _SOURCE_QUERY

        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            ScdType7Hybrid(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                key_columns=_KEY_COLS,
                tracked_columns=_TRACKED_COLS,
                current_columns=_CURRENT_COLS,
                _config=KnotConfig(id="scd7h"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["scd7h"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_src()
        self._tmp = tempfile.TemporaryDirectory()
        self.tgt = SqlitePool(
            SqliteConfig(database=str(Path(self._tmp.name) / "tgt.db"))
        )
        await self.tgt.execute(
            "CREATE TABLE customers ("
            "  id INTEGER NOT NULL,"
            "  region TEXT NOT NULL,"
            "  current_region TEXT,"
            "  valid_from TEXT NOT NULL,"
            "  valid_to TEXT,"
            "  is_current INTEGER NOT NULL"
            ")"
        )

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()
        self._tmp.cleanup()

    def _make_knot(self, **kwargs: Any) -> ScdType7Hybrid:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "key_columns": _KEY_COLS,
            "tracked_columns": _TRACKED_COLS,
            "current_columns": _CURRENT_COLS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return ScdType7Hybrid(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: ScdType7Hybrid, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "key_columns": _KEY_COLS,
            "tracked_columns": _TRACKED_COLS,
            "current_columns": _CURRENT_COLS,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_missing_current_column_mapping(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "missing entries"):
            await self._call(
                k,
                tracked_columns=("region", "country"),
                current_columns={"region": "current_region"},
            )

    async def test_rejects_overlap_key_and_tracked(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "overlap"):
            await self._call(
                k,
                key_columns=("id",),
                tracked_columns=("id", "region"),
                current_columns={"id": "current_id", "region": "current_region"},
            )

    async def test_static_query_helpers(self) -> None:
        k = self._make_knot()
        assert "dim_customer" in ScdType7Hybrid._select_current_query(
            "dim_customer", ("id",), ("region",), "is_current"
        )
        assert "dim_customer" in ScdType7Hybrid._close_out_query(
            "dim_customer", ("id",), "valid_to", "is_current"
        )
        assert "INSERT INTO dim_customer" in ScdType7Hybrid._insert_query(
            "dim_customer", ("id", "region"), ("current_region",),
            "valid_from", "valid_to", "is_current"
        )
        assert "current_region" in ScdType7Hybrid._insert_query(
            "dim_customer", ("id", "region"), ("current_region",),
            "valid_from", "valid_to", "is_current"
        )
        _ = k
