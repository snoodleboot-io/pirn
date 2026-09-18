"""Tests for DataProfile."""

from __future__ import annotations

import unittest
from datetime import datetime

from pirn_data.column_profile import ColumnProfile
from pirn_data.data_profile import DataProfile


class TestDataProfileConstruction(unittest.TestCase):
    def test_required_fields(self) -> None:
        dp = DataProfile(row_count=100, column_count=3)
        self.assertEqual(dp.row_count, 100)
        self.assertEqual(dp.column_count, 3)
        self.assertEqual(dp.columns, ())
        self.assertIsInstance(dp.sampled_at, datetime)

    def test_with_columns(self) -> None:
        cp = ColumnProfile("id", 10, 0, 10)
        dp = DataProfile(row_count=10, column_count=1, columns=(cp,))
        self.assertEqual(len(dp.columns), 1)
        self.assertEqual(dp.columns[0].name, "id")

    def test_column_lookup_found(self) -> None:
        cp = ColumnProfile("name", 10, 0, 5)
        dp = DataProfile(row_count=10, column_count=1, columns=(cp,))
        result = dp.column("name")
        self.assertIs(result, cp)

    def test_column_lookup_not_found(self) -> None:
        dp = DataProfile(row_count=0, column_count=0)
        self.assertIsNone(dp.column("nonexistent"))

    def test_frozen(self) -> None:
        dp = DataProfile(row_count=0, column_count=0)
        with self.assertRaises((AttributeError, TypeError)):
            dp.row_count = 1
