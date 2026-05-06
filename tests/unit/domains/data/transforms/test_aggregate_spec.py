"""Tests for AggregateSpec."""

from __future__ import annotations

import unittest

from pirn.domains.data.transforms.aggregate_spec import AggregateSpec


class TestAggregateSpecConstruction(unittest.TestCase):
    def test_valid_spec(self) -> None:
        for fn in ("sum", "mean", "min", "max", "count", "count_distinct", "first", "last"):
            with self.subTest(fn=fn):
                s = AggregateSpec(source="amount", function=fn)
                self.assertEqual(s.source, "amount")
                self.assertEqual(s.function, fn)

    def test_empty_source_raises(self) -> None:
        with self.assertRaises(ValueError):
            AggregateSpec(source="", function="sum")

    def test_invalid_function_raises(self) -> None:
        with self.assertRaises(ValueError):
            AggregateSpec(source="x", function="median")

    def test_frozen(self) -> None:
        s = AggregateSpec(source="x", function="sum")
        with self.assertRaises((AttributeError, TypeError)):
            s.source = "y"  # type: ignore[misc]

    def test_allowed_functions_is_tuple(self) -> None:
        fns = AggregateSpec._allowed_functions()
        self.assertIsInstance(fns, tuple)
        self.assertIn("sum", fns)
        self.assertIn("count_distinct", fns)

    def test_equality(self) -> None:
        a = AggregateSpec(source="x", function="sum")
        b = AggregateSpec(source="x", function="sum")
        self.assertEqual(a, b)
