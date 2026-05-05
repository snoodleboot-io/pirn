"""Tests for :class:`SilverCleanTransform`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.medallion.silver_clean_transform import (
    SilverCleanTransform,
)


def _make_pool() -> MagicMock:
    return MagicMock(spec=DatabaseConnectionPool)


class TestSilverCleanTransformConstruction(unittest.TestCase):
    def _make_valid(self) -> SilverCleanTransform:
        return SilverCleanTransform(
            source_pool=_make_pool(),
            source_query="SELECT id, name FROM bronze_t",
            target_pool=_make_pool(),
            target_table="silver_t",
            column_names=["id", "name"],
            casts={"id": int},
            filter_predicate=lambda row: bool(row.get("id")),
            primary_keys=["id"],
            _config=KnotConfig(id="silver"),
        )

    def test_valid_construction(self) -> None:
        sct = self._make_valid()
        self.assertIsInstance(sct, SilverCleanTransform)

    def test_rejects_non_pool_source(self) -> None:
        with self.assertRaises(TypeError):
            SilverCleanTransform(
                source_pool="not-pool",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=_make_pool(),
                target_table="silver_t",
                column_names=["id"],
                casts={},
                filter_predicate=lambda r: True,
                primary_keys=["id"],
                _config=KnotConfig(id="silver"),
            )

    def test_rejects_empty_source_query(self) -> None:
        with self.assertRaises(ValueError):
            SilverCleanTransform(
                source_pool=_make_pool(),
                source_query="",
                target_pool=_make_pool(),
                target_table="silver_t",
                column_names=["id"],
                casts={},
                filter_predicate=lambda r: True,
                primary_keys=["id"],
                _config=KnotConfig(id="silver"),
            )

    def test_rejects_empty_column_names(self) -> None:
        with self.assertRaises(ValueError):
            SilverCleanTransform(
                source_pool=_make_pool(),
                source_query="SELECT 1",
                target_pool=_make_pool(),
                target_table="silver_t",
                column_names=[],
                casts={},
                filter_predicate=lambda r: True,
                primary_keys=["id"],
                _config=KnotConfig(id="silver"),
            )

    def test_rejects_empty_primary_keys(self) -> None:
        with self.assertRaises(ValueError):
            SilverCleanTransform(
                source_pool=_make_pool(),
                source_query="SELECT 1",
                target_pool=_make_pool(),
                target_table="silver_t",
                column_names=["id"],
                casts={},
                filter_predicate=lambda r: True,
                primary_keys=[],
                _config=KnotConfig(id="silver"),
            )

    def test_insert_query_references_target_table(self) -> None:
        sct = self._make_valid()
        self.assertIn("silver_t", sct._insert_query)
