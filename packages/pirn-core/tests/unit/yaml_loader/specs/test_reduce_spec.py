"""Tests for ReduceSpec."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from pirn.yaml_loader.specs.reduce_spec import ReduceSpec


class TestReduceSpecConstruction(unittest.TestCase):
    def test_minimal(self) -> None:
        s = ReduceSpec(id="r1", type="reduce", of="map1", combine="mymod.combine")
        self.assertEqual(s.of, "map1")
        self.assertEqual(s.combine, "mymod.combine")
        self.assertIsNone(s.initial)
        self.assertFalse(s.has_initial)

    def test_with_initial(self) -> None:
        s = ReduceSpec(
            id="r2",
            type="reduce",
            of="map1",
            combine="fn",
            initial=0,
            has_initial=True,
        )
        self.assertEqual(s.initial, 0)
        self.assertTrue(s.has_initial)

    def test_initial_none_allowed(self) -> None:
        s = ReduceSpec(
            id="r3",
            type="reduce",
            of="map1",
            combine="fn",
            initial=None,
            has_initial=True,
        )
        self.assertIsNone(s.initial)
        self.assertTrue(s.has_initial)

    def test_wrong_type_raises(self) -> None:
        with self.assertRaises(ValidationError):
            ReduceSpec(id="x", type="knot", of="m", combine="fn")

    def test_missing_of_raises(self) -> None:
        with self.assertRaises(ValidationError):
            ReduceSpec(id="x", type="reduce", combine="fn")
