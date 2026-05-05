"""Tests for :class:`ScdType2MergeKnot`."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.scd.scd_type_2_merge_knot import (
    ScdType2MergeKnot,
)


def _make_pool() -> MagicMock:
    pool = MagicMock(spec=DatabaseConnectionPool)
    pool.fetch_all = AsyncMock(return_value=[])
    pool.execute_many = AsyncMock(return_value=None)
    return pool


class TestScdType2MergeKnotConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        knot = ScdType2MergeKnot(
            rows=MagicMock(),
            target_pool=_make_pool(),
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "region"],
            effective_date_column="valid_from",
            expiry_date_column="valid_to",
            current_flag_column="is_current",
            _config=KnotConfig(id="scd2"),
        )
        self.assertIsInstance(knot, ScdType2MergeKnot)

    def test_rejects_non_pool(self) -> None:
        with self.assertRaises(TypeError):
            ScdType2MergeKnot(
                rows=MagicMock(),
                target_pool="not-pool",  # type: ignore[arg-type]
                target_table="dim_customer",
                primary_keys=["id"],
                column_names=["id", "region"],
                effective_date_column="valid_from",
                expiry_date_column="valid_to",
                current_flag_column="is_current",
                _config=KnotConfig(id="scd2"),
            )

    def test_rejects_pk_not_in_columns(self) -> None:
        with self.assertRaises(ValueError):
            ScdType2MergeKnot(
                rows=MagicMock(),
                target_pool=_make_pool(),
                target_table="dim_customer",
                primary_keys=["missing"],
                column_names=["id", "region"],
                effective_date_column="valid_from",
                expiry_date_column="valid_to",
                current_flag_column="is_current",
                _config=KnotConfig(id="scd2"),
            )

    def test_rejects_scd_columns_in_column_names(self) -> None:
        with self.assertRaises(ValueError):
            ScdType2MergeKnot(
                rows=MagicMock(),
                target_pool=_make_pool(),
                target_table="dim_customer",
                primary_keys=["id"],
                column_names=["id", "region", "valid_from"],
                effective_date_column="valid_from",
                expiry_date_column="valid_to",
                current_flag_column="is_current",
                _config=KnotConfig(id="scd2"),
            )


class TestScdType2MergeKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_zeros_for_empty_rows(self) -> None:
        knot = ScdType2MergeKnot(
            rows=MagicMock(),
            target_pool=_make_pool(),
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "region"],
            effective_date_column="valid_from",
            expiry_date_column="valid_to",
            current_flag_column="is_current",
            _config=KnotConfig(id="scd2"),
        )
        result = await knot.process(rows=[], **{})
        self.assertEqual(result, {"inserted": 0, "expired": 0})

    async def test_inserts_new_rows(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[])
        pool.execute_many = AsyncMock(return_value=None)
        knot = ScdType2MergeKnot(
            rows=MagicMock(),
            target_pool=pool,
            target_table="dim_customer",
            primary_keys=["id"],
            column_names=["id", "region"],
            effective_date_column="valid_from",
            expiry_date_column="valid_to",
            current_flag_column="is_current",
            _config=KnotConfig(id="scd2"),
        )
        result = await knot.process(rows=[(1, "EU"), (2, "US")], **{})
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(result["expired"], 0)
