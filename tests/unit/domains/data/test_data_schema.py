"""Tests for DataSchema."""

from __future__ import annotations

import unittest

from pirn.domains.data.data_schema import DataSchema


class TestDataSchemaConstruction(unittest.TestCase):
    def test_empty_schema(self) -> None:
        s = DataSchema()
        self.assertEqual(s.columns, {})
        self.assertEqual(s.primary_keys, ())
        self.assertEqual(s.nullable, ())

    def test_with_columns(self) -> None:
        s = DataSchema(columns={"id": int, "name": str})
        self.assertEqual(s.columns["id"], int)
        self.assertEqual(s.columns["name"], str)

    def test_column_names_property(self) -> None:
        s = DataSchema(columns={"a": int, "b": str})
        self.assertEqual(s.column_names, ("a", "b"))

    def test_primary_keys_validation(self) -> None:
        with self.assertRaises(ValueError):
            DataSchema(columns={"id": int}, primary_keys=("missing_col",))

    def test_nullable_validation(self) -> None:
        with self.assertRaises(ValueError):
            DataSchema(columns={"id": int}, nullable=("missing_col",))

    def test_valid_primary_keys(self) -> None:
        s = DataSchema(columns={"id": int, "name": str}, primary_keys=("id",))
        self.assertEqual(s.primary_keys, ("id",))

    def test_is_nullable_true(self) -> None:
        s = DataSchema(columns={"x": str}, nullable=("x",))
        self.assertTrue(s.is_nullable("x"))

    def test_is_nullable_false(self) -> None:
        s = DataSchema(columns={"x": str})
        self.assertFalse(s.is_nullable("x"))

    def test_with_columns_merge(self) -> None:
        s = DataSchema(columns={"a": int})
        s2 = s.with_columns({"b": str})
        self.assertIn("a", s2.columns)
        self.assertIn("b", s2.columns)

    def test_with_columns_override(self) -> None:
        s = DataSchema(columns={"a": int})
        s2 = s.with_columns({"a": str})
        self.assertEqual(s2.columns["a"], str)

    def test_pirn_audit_dict(self) -> None:
        s = DataSchema(columns={"id": int}, primary_keys=("id",), nullable=())
        d = s._pirn_audit_dict()
        self.assertEqual(d["columns"], {"id": "int"})
        self.assertEqual(d["primary_keys"], ["id"])

    def test_pirn_canonical(self) -> None:
        s = DataSchema(columns={"x": float})
        c = s.__pirn_canonical__()
        self.assertEqual(c["columns"], {"x": "float"})
