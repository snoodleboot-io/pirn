"""Tests for ColumnProfile."""

from __future__ import annotations

import unittest

from pirn_data.column_profile import ColumnProfile


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
            cp.name = "y"
