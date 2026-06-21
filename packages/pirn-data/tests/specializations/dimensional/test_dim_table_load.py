"""Tests for :class:`DimTableLoad`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.dimensional.dim_table_load import DimTableLoad

_SOURCE_QUERY = "SELECT id, name, region FROM customers"
_TARGET_TABLE = "customers"
_NK_COLS = ("id",)
_NON_KEY_COLS = ("name", "region")


async def _make_source_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE customers ("
        "  id INTEGER PRIMARY KEY,"
        "  name TEXT NOT NULL,"
        "  region TEXT NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO customers (id, name, region) VALUES (?, ?, ?)",
        [(1, "Alice", "EU"), (2, "Bob", "US")],
    )
    return pool


async def _make_target_type1() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE customers ("
        "  dim_sk INTEGER PRIMARY KEY,"
        "  id INTEGER NOT NULL,"
        "  name TEXT NOT NULL,"
        "  region TEXT NOT NULL"
        ")"
    )
    return pool


async def _make_target_type2() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE customers ("
        "  dim_sk INTEGER NOT NULL,"
        "  id INTEGER NOT NULL,"
        "  name TEXT NOT NULL,"
        "  region TEXT NOT NULL,"
        "  valid_from TEXT NOT NULL,"
        "  valid_to TEXT,"
        "  is_current INTEGER NOT NULL"
        ")"
    )
    return pool


def _make_knot(
    src: SqlitePool, tgt: SqlitePool, **overrides: Any
) -> DimTableLoad:
    defaults: dict[str, Any] = {
        "source_pool": src,
        "source_query": _SOURCE_QUERY,
        "target_pool": tgt,
        "target_table": _TARGET_TABLE,
        "natural_key_columns": _NK_COLS,
        "non_key_columns": _NON_KEY_COLS,
        "surrogate_key_column": "dim_sk",
        "scd_type": 1,
        "valid_from_column": "valid_from",
        "valid_to_column": "valid_to",
        "current_flag_column": "is_current",
    }
    defaults.update(overrides)
    return DimTableLoad(**defaults, _config=KnotConfig(id="dim"))


class TestDimTableLoad(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_source_pool()
        self.tgt = await _make_target_type1()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_inserts_with_surrogate_keys(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT dim_sk, id, name, region FROM customers ORDER BY id"
        )
        assert len(rows) == 2
        assert rows[0][0] == 1
        assert rows[1][0] == 2

    async def test_updates_on_second_run(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        assert (await t.run(RunRequest())).succeeded
        await self.src.execute(
            "UPDATE customers SET region = ? WHERE id = ?", ("APAC", 1)
        )
        with Tapestry() as t2:
            _make_knot(self.src, self.tgt)
        assert (await t2.run(RunRequest())).succeeded
        rows = await self.tgt.fetch_all("SELECT region FROM customers WHERE id = 1")
        assert rows[0][0] == "APAC"
        count = await self.tgt.fetch_all("SELECT COUNT(*) FROM customers")
        assert count[0][0] == 2

    async def test_type2_inserts_with_history_columns(self) -> None:
        tgt2 = await _make_target_type2()
        with Tapestry() as t:
            _make_knot(self.src, tgt2, scd_type=2)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await tgt2.fetch_all(
            "SELECT id, valid_to, is_current FROM customers ORDER BY id"
        )
        assert len(rows) == 2
        for row in rows:
            assert row[1] is None
            assert row[2] == 1
        await tgt2.close()

    async def test_type2_expires_old_row_on_change(self) -> None:
        tgt2 = await _make_target_type2()
        with Tapestry() as t:
            _make_knot(self.src, tgt2, scd_type=2)
        assert (await t.run(RunRequest())).succeeded
        await self.src.execute(
            "UPDATE customers SET region = ? WHERE id = ?", ("APAC", 1)
        )
        with Tapestry() as t2:
            _make_knot(self.src, tgt2, scd_type=2)
        assert (await t2.run(RunRequest())).succeeded
        rows = await tgt2.fetch_all(
            "SELECT id, region, is_current FROM customers ORDER BY id, valid_from"
        )
        assert len(rows) == 3
        old_alice = next(r for r in rows if r[0] == 1 and r[2] == 0)
        assert old_alice[1] == "EU"
        new_alice = next(r for r in rows if r[0] == 1 and r[2] == 1)
        assert new_alice[1] == "APAC"
        await tgt2.close()


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_source_pool()
        self.tgt = await _make_target_type1()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_source_query_from_upstream_knot(self) -> None:
        @knot
        async def emit_query() -> str:
            return _SOURCE_QUERY

        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            DimTableLoad(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                natural_key_columns=_NK_COLS,
                non_key_columns=_NON_KEY_COLS,
                surrogate_key_column="dim_sk",
                scd_type=1,
                valid_from_column="valid_from",
                valid_to_column="valid_to",
                current_flag_column="is_current",
                _config=KnotConfig(id="dim"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["dim"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_source_pool()
        self.tgt = await _make_target_type1()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> DimTableLoad:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "natural_key_columns": _NK_COLS,
            "non_key_columns": _NON_KEY_COLS,
            "surrogate_key_column": "dim_sk",
            "scd_type": 1,
            "valid_from_column": "valid_from",
            "valid_to_column": "valid_to",
            "current_flag_column": "is_current",
        }
        defaults.update(kwargs)
        with Tapestry():
            return DimTableLoad(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: DimTableLoad, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "natural_key_columns": _NK_COLS,
            "non_key_columns": _NON_KEY_COLS,
            "surrogate_key_column": "dim_sk",
            "scd_type": 1,
            "valid_from_column": "valid_from",
            "valid_to_column": "valid_to",
            "current_flag_column": "is_current",
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_invalid_scd_type(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "scd_type"):
            await self._call(k, scd_type=3)

    async def test_rejects_invalid_target_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, target_table="bad table")

    async def test_rejects_empty_source_query(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_query"):
            await self._call(k, source_query="")
