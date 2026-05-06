from __future__ import annotations

import unittest

from pirn.core.parameter_spec import ParameterSpec


class TestParameterSpec(unittest.TestCase):
    def test_minimal_construction(self) -> None:
        spec = ParameterSpec(name="x", type_=int)
        self.assertEqual(spec.name, "x")
        self.assertEqual(spec.type_, int)
        self.assertFalse(spec.has_default)
        self.assertIsNone(spec.default)
        self.assertIsNone(spec.description)

    def test_with_default(self) -> None:
        spec = ParameterSpec(name="x", type_=int, has_default=True, default=42)
        self.assertTrue(spec.has_default)
        self.assertEqual(spec.default, 42)

    def test_with_description(self) -> None:
        spec = ParameterSpec(name="x", type_=str, description="a param")
        self.assertEqual(spec.description, "a param")

    def test_complex_type(self) -> None:
        spec = ParameterSpec(name="items", type_=list[str])
        self.assertEqual(spec.type_, list[str])

    def test_none_default(self) -> None:
        spec = ParameterSpec(name="x", type_=int, has_default=True, default=None)
        self.assertIsNone(spec.default)
        self.assertTrue(spec.has_default)

    def test_frozen(self) -> None:
        spec = ParameterSpec(name="x", type_=int)
        with self.assertRaises(Exception):
            spec.name = "y"

    def test_arbitrary_types_allowed(self) -> None:
        class CustomType:
            pass

        spec = ParameterSpec(name="x", type_=CustomType)
        self.assertIs(spec.type_, CustomType)
