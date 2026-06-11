"""Tests for YamlParameterSpec."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from pirn.yaml_loader.specs.yaml_parameter_spec import YamlParameterSpec


class TestParameterSpecConstruction(unittest.TestCase):
    def test_minimal(self) -> None:
        s = YamlParameterSpec(id="p1", type="parameter", type_="int")
        self.assertEqual(s.id, "p1")
        self.assertEqual(s.type_, "int")
        self.assertIsNone(s.default)
        self.assertFalse(s.has_default)

    def test_with_default(self) -> None:
        s = YamlParameterSpec(id="p2", type="parameter", type_="str", default="hello", has_default=True)
        self.assertEqual(s.default, "hello")
        self.assertTrue(s.has_default)

    def test_default_none_allowed(self) -> None:
        s = YamlParameterSpec(id="p3", type="parameter", type_="int", default=None, has_default=True)
        self.assertIsNone(s.default)
        self.assertTrue(s.has_default)

    def test_wrong_type_literal_raises(self) -> None:
        with self.assertRaises(ValidationError):
            YamlParameterSpec(id="x", type="knot", type_="int")

    def test_missing_type_field_raises(self) -> None:
        with self.assertRaises(ValidationError):
            YamlParameterSpec(id="x", type="parameter")

    def test_dotted_type_path(self) -> None:
        s = YamlParameterSpec(id="p4", type="parameter", type_="list[dict]")
        self.assertEqual(s.type_, "list[dict]")
