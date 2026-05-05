"""Tests for :class:`ScdType1MergeKnot`."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.scd.scd_type_1_merge_knot import (
    ScdType1MergeKnot,
)


def _make_pool() -> MagicMock:
    pool = MagicMock(spec=DatabaseConnectionPool)
    pool.fetch_all = AsyncMock(return_value=[])
    pool.execute_many = AsyncMock(return_value=None)
    return pool


class TestScdType1MergeKnotConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        pool = _make_pool()
        knot = ScdType1MergeKnot(
            rows=MagicMock(),
            target_pool=pool,
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "name", "region"],
            _config=KnotConfig(id="scd1"),
        )
        self.assertIsInstance(knot, ScdType1MergeKnot)

    def test_rejects_non_pool(self) -> None:
        with self.assertRaises(TypeError):
            ScdType1MergeKnot(
                rows=MagicMock(),
                target_pool="not-pool",  # type: ignore[arg-type]
                target_table="dim_customer",
                primary_keys=["id"],
                column_names=["id", "name"],
                _config=KnotConfig(id="scd1"),
            )

    def test_rejects_pk_not_in_columns(self) -> None:
        pool = _make_pool()
        with self.assertRaises(ValueError):
            ScdType1MergeKnot(
                rows=MagicMock(),
                target_pool=pool,
                target_table="dim_customer",
                primary_keys=["missing_key"],
                column_names=["id", "name"],
                _config=KnotConfig(id="scd1"),
            )

    def test_query_properties(self) -> None:
        pool = _make_pool()
        knot = ScdType1MergeKnot(
            rows=MagicMock(),
            target_pool=pool,
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "name"],
            _config=KnotConfig(id="scd1"),
        )
        self.assertIn("dim_customer", knot.select_query)
        self.assertIn("INSERT INTO dim_customer", knot.insert_query)
        self.assertIn("UPDATE dim_customer", knot.update_query)


class TestScdType1MergeKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_zeros_for_empty_rows(self) -> None:
        pool = _make_pool()
        knot = ScdType1MergeKnot(
            rows=MagicMock(),
            target_pool=pool,
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "name"],
            _config=KnotConfig(id="scd1"),
        )
        result = await knot.process(rows=[], **{})
        self.assertEqual(result, {"inserted": 0, "updated": 0})

    async def test_inserts_new_rows(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[])
        pool.execute_many = AsyncMock(return_value=None)
        knot = ScdType1MergeKnot(
            rows=MagicMock(),
            target_pool=pool,
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "name"],
            _config=KnotConfig(id="scd1"),
        )
        result = await knot.process(rows=[(1, "alice"), (2, "bob")], **{})
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(result["updated"], 0)

    async def test_updates_changed_rows(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[(1, "alice_old")])
        pool.execute_many = AsyncMock(return_value=None)
        knot = ScdType1MergeKnot(
            rows=MagicMock(),
            target_pool=pool,
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "name"],
            _config=KnotConfig(id="scd1"),
        )
        result = await knot.process(rows=[(1, "alice_new")], **{})
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["inserted"], 0)

    async def test_skips_unchanged_rows(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[(1, "alice")])
        pool.execute_many = AsyncMock(return_value=None)
        knot = ScdType1MergeKnot(
            rows=MagicMock(),
            target_pool=pool,
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "name"],
            _config=KnotConfig(id="scd1"),
        )
        result = await knot.process(rows=[(1, "alice")], **{})
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["updated"], 0)
