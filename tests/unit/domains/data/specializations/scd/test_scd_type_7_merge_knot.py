"""Tests for :class:`ScdType7MergeKnot`."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.scd.scd_type_7_merge_knot import (
    ScdType7MergeKnot,
)


def _make_pool() -> MagicMock:
    pool = MagicMock(spec=DatabaseConnectionPool)
    pool.fetch_all = AsyncMock(return_value=[])
    pool.execute_many = AsyncMock(return_value=None)
    return pool


class TestScdType7MergeKnotConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        knot = ScdType7MergeKnot(
            rows=MagicMock(),
            target_pool=_make_pool(),
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "region"],
            surrogate_key_column="scd_id",
            effective_date_column="valid_from",
            expiry_date_column="valid_to",
            current_flag_column="is_current",
            _config=KnotConfig(id="scd7"),
        )
        self.assertIsInstance(knot, ScdType7MergeKnot)

    def test_rejects_non_pool(self) -> None:
        with self.assertRaises(TypeError):
            ScdType7MergeKnot(
                rows=MagicMock(),
                target_pool="not-pool",  # type: ignore[arg-type]
                target_table="dim_customer",
                primary_keys=["id"],
                column_names=["id", "region"],
                surrogate_key_column="scd_id",
                effective_date_column="valid_from",
                expiry_date_column="valid_to",
                current_flag_column="is_current",
                _config=KnotConfig(id="scd7"),
            )

    def test_rejects_pk_not_in_columns(self) -> None:
        with self.assertRaises(ValueError):
            ScdType7MergeKnot(
                rows=MagicMock(),
                target_pool=_make_pool(),
                target_table="dim_customer",
                primary_keys=["missing"],
                column_names=["id", "region"],
                surrogate_key_column="scd_id",
                effective_date_column="valid_from",
                expiry_date_column="valid_to",
                current_flag_column="is_current",
                _config=KnotConfig(id="scd7"),
            )

    def test_rejects_bookkeeping_columns_in_column_names(self) -> None:
        with self.assertRaises(ValueError):
            ScdType7MergeKnot(
                rows=MagicMock(),
                target_pool=_make_pool(),
                target_table="dim_customer",
                primary_keys=["id"],
                column_names=["id", "region", "scd_id"],
                surrogate_key_column="scd_id",
                effective_date_column="valid_from",
                expiry_date_column="valid_to",
                current_flag_column="is_current",
                _config=KnotConfig(id="scd7"),
            )


class TestScdType7MergeKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_zeros_for_empty_rows(self) -> None:
        pool = _make_pool()
        knot = ScdType7MergeKnot(
            rows=MagicMock(),
            target_pool=pool,
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "region"],
            surrogate_key_column="scd_id",
            effective_date_column="valid_from",
            expiry_date_column="valid_to",
            current_flag_column="is_current",
            _config=KnotConfig(id="scd7"),
        )
        result = await knot.process(rows=[], **{})
        self.assertEqual(result, {"inserted": 0, "expired": 0})

    async def test_inserts_new_rows_with_surrogate(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(side_effect=[[], [(0,)]])
        pool.execute_many = AsyncMock(return_value=None)
        knot = ScdType7MergeKnot(
            rows=MagicMock(),
            target_pool=pool,
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "region"],
            surrogate_key_column="scd_id",
            effective_date_column="valid_from",
            expiry_date_column="valid_to",
            current_flag_column="is_current",
            _config=KnotConfig(id="scd7"),
        )
        result = await knot.process(rows=[(1, "EU")], **{})
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["expired"], 0)
