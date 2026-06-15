"""Tests for MapSpec."""

from __future__ import annotations

import unittest

from pirn.yaml_loader.specs.map_spec import MapSpec
from pydantic import ValidationError


class TestMapSpecConstruction(unittest.TestCase):
    def test_minimal(self) -> None:
        s = MapSpec(id="m1", type="map", over="source1", each="mymod.fn", bind="item")
        self.assertEqual(s.over, "source1")
        self.assertEqual(s.each, "mymod.fn")
        self.assertEqual(s.bind, "item")
        self.assertEqual(s.shared, {})

    def test_with_shared(self) -> None:
        s = MapSpec(
            id="m2",
            type="map",
            over="src",
            each="fn",
            bind="row",
            shared={"cfg": "config_knot", "limit": 50},
        )
        self.assertEqual(s.shared["cfg"], "config_knot")
        self.assertEqual(s.shared["limit"], 50)

    def test_wrong_type_raises(self) -> None:
        with self.assertRaises(ValidationError):
            MapSpec(id="x", type="knot", over="src", each="fn", bind="item")

    def test_missing_over_raises(self) -> None:
        with self.assertRaises(ValidationError):
            MapSpec(id="x", type="map", each="fn", bind="item")

    def test_missing_each_raises(self) -> None:
        with self.assertRaises(ValidationError):
            MapSpec(id="x", type="map", over="src", bind="item")

    def test_missing_bind_raises(self) -> None:
        with self.assertRaises(ValidationError):
            MapSpec(id="x", type="map", over="src", each="fn")
