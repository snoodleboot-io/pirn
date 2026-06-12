"""Tests for :class:`ScdType2MergeKnot`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.scd.scd_type_2_merge_knot import ScdType2MergeKnot
from pirn.tapestry import Tapestry

_TARGET_TABLE = "dim_customer"
_PRIMARY_KEYS = ("id",)
_COLUMN_NAMES = ("id", "region")
_EFF_COL = "valid_from"
_EXP_COL = "valid_to"
_FLAG_COL = "is_current"


def _make_pool() -> MagicMock:
    pool = MagicMock(spec=DatabaseConnectionPool)
    pool.fetch_all = AsyncMock(return_value=[])
    pool.execute_many = AsyncMock(return_value=None)
    return pool


def _make_knot(pool: MagicMock | None = None, **kwargs: Any) -> ScdType2MergeKnot:
    if pool is None:
        pool = _make_pool()
    defaults: dict[str, Any] = {
        "rows": MagicMock(),
        "target_pool": pool,
        "target_table": _TARGET_TABLE,
        "primary_keys": _PRIMARY_KEYS,
        "column_names": _COLUMN_NAMES,
        "effective_date_column": _EFF_COL,
        "expiry_date_column": _EXP_COL,
        "current_flag_column": _FLAG_COL,
    }
    defaults.update(kwargs)
    with Tapestry():
        return ScdType2MergeKnot(**defaults, _config=KnotConfig(id="scd2"))


class TestScdType2MergeKnotConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        self.assertIsInstance(_make_knot(), ScdType2MergeKnot)

    def test_static_query_methods(self) -> None:
        self.assertIn(
            "dim_customer",
            ScdType2MergeKnot._select_query("dim_customer", ("id", "region"), "is_current"),
        )
        self.assertIn(
            "INSERT INTO dim_customer",
            ScdType2MergeKnot._insert_query(
                "dim_customer", ("id", "region"), "valid_from", "valid_to", "is_current"
            ),
        )
        self.assertIn(
            "dim_customer",
            ScdType2MergeKnot._expire_query(
                "dim_customer", ("id",), "valid_to", "is_current"
            ),
        )


class TestScdType2MergeKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def _call(
        self, k: ScdType2MergeKnot, rows: Any, pool: MagicMock, **overrides: Any
    ) -> dict[str, int]:
        args: dict[str, Any] = {
            "rows": rows,
            "target_pool": pool,
            "target_table": _TARGET_TABLE,
            "primary_keys": _PRIMARY_KEYS,
            "column_names": _COLUMN_NAMES,
            "effective_date_column": _EFF_COL,
            "expiry_date_column": _EXP_COL,
            "current_flag_column": _FLAG_COL,
        }
        args.update(overrides)
        return await k.process(**args)

    async def test_returns_zeros_for_empty_rows(self) -> None:
        pool = _make_pool()
        k = _make_knot(pool)
        result = await self._call(k, [], pool)
        self.assertEqual(result, {"inserted": 0, "expired": 0})

    async def test_inserts_new_rows(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[])
        k = _make_knot(pool)
        result = await self._call(k, [(1, "EU"), (2, "US")], pool)
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(result["expired"], 0)

    async def test_expires_and_inserts_changed_row(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[(1, "EU")])
        k = _make_knot(pool)
        result = await self._call(k, [(1, "APAC")], pool)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["expired"], 1)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _call(self, k: ScdType2MergeKnot, **overrides: Any) -> Any:
        pool = _make_pool()
        args: dict[str, Any] = {
            "rows": [],
            "target_pool": pool,
            "target_table": _TARGET_TABLE,
            "primary_keys": _PRIMARY_KEYS,
            "column_names": _COLUMN_NAMES,
            "effective_date_column": _EFF_COL,
            "expiry_date_column": _EXP_COL,
            "current_flag_column": _FLAG_COL,
        }
        args.update(overrides)
        return await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await self._call(k, target_pool="not-pool", rows=[(1, "EU")])

    async def test_rejects_pk_not_in_columns(self) -> None:
        k = _make_knot()
        with self.assertRaises(ValueError):
            await self._call(k, primary_keys=("missing",), rows=[(1, "EU")])

    async def test_rejects_scd_columns_in_column_names(self) -> None:
        k = _make_knot()
        with self.assertRaises(ValueError):
            await self._call(
                k,
                column_names=("id", "region", "valid_from"),
                rows=[(1, "EU", "2020-01-01")],
            )
