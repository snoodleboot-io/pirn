"""Tests for DataProfile and ColumnProfile."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pirn.domains.data.data_profile import ColumnProfile, DataProfile


class TestColumnProfileConstruction(unittest.TestCase):
    def test_required_fields(self) -> None:
        cp = ColumnProfile(
            name="age",
            observed_count=100,
            null_count=5,
            distinct_count=80,
        )
        self.assertEqual(cp.name, "age")
        self.assertEqual(cp.observed_count, 100)
        self.assertEqual(cp.null_count, 5)
        self.assertEqual(cp.distinct_count, 80)
        self.assertIsNone(cp.min_value)
        self.assertIsNone(cp.max_value)
        self.assertIsNone(cp.top_value)
        self.assertEqual(cp.top_value_count, 0)

    def test_optional_fields(self) -> None:
        cp = ColumnProfile(
            name="score",
            observed_count=50,
            null_count=0,
            distinct_count=50,
            min_value=0,
            max_value=100,
            top_value=42,
            top_value_count=3,
        )
        self.assertEqual(cp.min_value, 0)
        self.assertEqual(cp.max_value, 100)
        self.assertEqual(cp.top_value, 42)
        self.assertEqual(cp.top_value_count, 3)

    def test_frozen(self) -> None:
        cp = ColumnProfile("x", 10, 0, 10)
        with self.assertRaises((AttributeError, TypeError)):
            cp.name = "y"  # type: ignore[misc]


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
            dp.row_count = 1  # type: ignore[misc]
