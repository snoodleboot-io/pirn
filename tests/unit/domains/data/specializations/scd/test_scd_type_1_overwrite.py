"""Tests for :class:`ScdType1Overwrite`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.scd.scd_type_1_overwrite import (
    ScdType1Overwrite,
)


def _make_pool() -> MagicMock:
    return MagicMock(spec=DatabaseConnectionPool)


class TestScdType1OverwriteConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        scd = ScdType1Overwrite(
            source_pool=_make_pool(),
            source_query="SELECT id, name FROM src",
            target_pool=_make_pool(),
            target_table="dim_customer",
            key_columns=["id"],
            non_key_columns=["name"],
            _config=KnotConfig(id="scd1ow"),
        )
        self.assertIsInstance(scd, ScdType1Overwrite)

    def test_rejects_non_pool_source(self) -> None:
        with self.assertRaises(TypeError):
            ScdType1Overwrite(
                source_pool="not-pool",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=_make_pool(),
                target_table="dim_customer",
                key_columns=["id"],
                non_key_columns=["name"],
                _config=KnotConfig(id="scd1ow"),
            )

    def test_rejects_overlap_key_and_non_key(self) -> None:
        with self.assertRaises(ValueError):
            ScdType1Overwrite(
                source_pool=_make_pool(),
                source_query="SELECT 1",
                target_pool=_make_pool(),
                target_table="dim_customer",
                key_columns=["id"],
                non_key_columns=["id", "name"],
                _config=KnotConfig(id="scd1ow"),
            )

    def test_query_properties(self) -> None:
        scd = ScdType1Overwrite(
            source_pool=_make_pool(),
            source_query="SELECT id, name FROM src",
            target_pool=_make_pool(),
            target_table="dim_customer",
            key_columns=["id"],
            non_key_columns=["name"],
            _config=KnotConfig(id="scd1ow"),
        )
        self.assertIn("dim_customer", scd.select_existing_query)
        self.assertIn("UPDATE dim_customer", scd.update_query)
        self.assertIn("INSERT INTO dim_customer", scd.insert_query)
