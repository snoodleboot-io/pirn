"""Tests for :class:`ScdType2History`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.scd.scd_type_2_history import ScdType2History


def _make_pool() -> MagicMock:
    return MagicMock(spec=DatabaseConnectionPool)


class TestScdType2HistoryConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        scd = ScdType2History(
            source_pool=_make_pool(),
            source_query="SELECT id, region FROM src",
            target_pool=_make_pool(),
            target_table="dim_customer",
            key_columns=["id"],
            tracked_columns=["region"],
            _config=KnotConfig(id="scd2"),
        )
        self.assertIsInstance(scd, ScdType2History)

    def test_rejects_non_pool_source(self) -> None:
        with self.assertRaises(TypeError):
            ScdType2History(
                source_pool="not-pool",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=_make_pool(),
                target_table="dim_customer",
                key_columns=["id"],
                tracked_columns=["region"],
                _config=KnotConfig(id="scd2"),
            )

    def test_rejects_overlap_key_and_tracked(self) -> None:
        with self.assertRaises(ValueError):
            ScdType2History(
                source_pool=_make_pool(),
                source_query="SELECT 1",
                target_pool=_make_pool(),
                target_table="dim_customer",
                key_columns=["id"],
                tracked_columns=["id", "region"],
                _config=KnotConfig(id="scd2"),
            )

    def test_query_properties(self) -> None:
        scd = ScdType2History(
            source_pool=_make_pool(),
            source_query="SELECT id, region FROM src",
            target_pool=_make_pool(),
            target_table="dim_customer",
            key_columns=["id"],
            tracked_columns=["region"],
            _config=KnotConfig(id="scd2"),
        )
        self.assertIn("dim_customer", scd.select_current_query)
        self.assertIn("dim_customer", scd.close_out_query)
        self.assertIn("INSERT INTO dim_customer", scd.insert_query)
