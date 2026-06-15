"""Tests for KnotSpec."""

from __future__ import annotations

import unittest

from pirn.yaml_loader.specs.knot_spec import KnotSpec
from pydantic import ValidationError


class TestKnotSpecConstruction(unittest.TestCase):
    def test_minimal(self) -> None:
        s = KnotSpec(id="k1", type="knot", callable="mymod.MyKnot")
        self.assertEqual(s.id, "k1")
        self.assertEqual(s.callable, "mymod.MyKnot")
        self.assertEqual(s.parents, {})
        self.assertEqual(s.config, {})

    def test_with_parents_and_config(self) -> None:
        s = KnotSpec(
            id="k2",
            type="knot",
            callable="mymod.fn",
            parents={"data": "source1"},
            config={"batch_size": 100},
        )
        self.assertEqual(s.parents, {"data": "source1"})
        self.assertEqual(s.config, {"batch_size": 100})

    def test_wrong_type_raises(self) -> None:
        with self.assertRaises(ValidationError):
            KnotSpec(id="x", type="source", callable="fn")

    def test_missing_callable_raises(self) -> None:
        with self.assertRaises(ValidationError):
            KnotSpec(id="x", type="knot")

    def test_config_any_value_type(self) -> None:
        s = KnotSpec(
            id="k3",
            type="knot",
            callable="fn",
            config={"key": [1, 2, 3], "nested": {"a": "b"}},
        )
        self.assertEqual(s.config["key"], [1, 2, 3])
