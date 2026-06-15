"""Tests for :class:`ScdType1MergeKnot`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_data.specializations.scd.scd_type_1_merge_knot import ScdType1MergeKnot

_TARGET_TABLE = "dim_customer"
_PRIMARY_KEYS = ("id",)
_COLUMN_NAMES = ("id", "name")


def _make_pool() -> MagicMock:
    pool = MagicMock(spec=DatabaseConnectionPool)
    pool.fetch_all = AsyncMock(return_value=[])
    pool.execute_many = AsyncMock(return_value=None)
    return pool


def _make_knot(pool: MagicMock | None = None, **kwargs: Any) -> ScdType1MergeKnot:
    if pool is None:
        pool = _make_pool()
    defaults: dict[str, Any] = {
        "rows": MagicMock(),
        "target_pool": pool,
        "target_table": _TARGET_TABLE,
        "primary_keys": _PRIMARY_KEYS,
        "column_names": _COLUMN_NAMES,
    }
    defaults.update(kwargs)
    with Tapestry():
        return ScdType1MergeKnot(**defaults, _config=KnotConfig(id="scd1"))


class TestScdType1MergeKnotConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        knot = _make_knot()
        self.assertIsInstance(knot, ScdType1MergeKnot)

    def test_query_static_methods(self) -> None:
        self.assertIn(
            "dim_customer",
            ScdType1MergeKnot._select_query("dim_customer", ("id", "name")),
        )
        self.assertIn(
            "INSERT INTO dim_customer",
            ScdType1MergeKnot._insert_query("dim_customer", ("id", "name")),
        )
        self.assertIn(
            "UPDATE dim_customer",
            ScdType1MergeKnot._update_query("dim_customer", ("id",), ("name",)),
        )


class TestScdType1MergeKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def _call(
        self, k: ScdType1MergeKnot, rows: Any, pool: MagicMock, **overrides: Any
    ) -> dict[str, int]:
        args: dict[str, Any] = {
            "rows": rows,
            "target_pool": pool,
            "target_table": _TARGET_TABLE,
            "primary_keys": _PRIMARY_KEYS,
            "column_names": _COLUMN_NAMES,
        }
        args.update(overrides)
        return await k.process(**args)

    async def test_returns_zeros_for_empty_rows(self) -> None:
        pool = _make_pool()
        k = _make_knot(pool)
        result = await self._call(k, [], pool)
        self.assertEqual(result, {"inserted": 0, "updated": 0})

    async def test_inserts_new_rows(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[])
        k = _make_knot(pool)
        result = await self._call(k, [(1, "alice"), (2, "bob")], pool)
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(result["updated"], 0)

    async def test_updates_changed_rows(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[(1, "alice_old")])
        k = _make_knot(pool)
        result = await self._call(k, [(1, "alice_new")], pool)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["inserted"], 0)

    async def test_skips_unchanged_rows(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[(1, "alice")])
        k = _make_knot(pool)
        result = await self._call(k, [(1, "alice")], pool)
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["updated"], 0)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _call(self, k: ScdType1MergeKnot, **overrides: Any) -> Any:
        pool = _make_pool()
        args: dict[str, Any] = {
            "rows": [],
            "target_pool": pool,
            "target_table": _TARGET_TABLE,
            "primary_keys": _PRIMARY_KEYS,
            "column_names": _COLUMN_NAMES,
        }
        args.update(overrides)
        return await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await self._call(k, target_pool="not-pool", rows=[(1, "a")])

    async def test_rejects_pk_not_in_columns(self) -> None:
        k = _make_knot()
        with self.assertRaises(ValueError):
            await self._call(
                k, primary_keys=("missing_key",), rows=[(1, "a")]
            )
