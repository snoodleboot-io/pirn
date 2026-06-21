"""Tests for IdentifierValidator."""

from __future__ import annotations

import unittest

from pirn_data.identifier_validator import IdentifierValidator


class TestIdentifierValidatorValidateColumn(unittest.TestCase):
    def test_valid_identifier(self) -> None:
        # Should not raise.
        IdentifierValidator.validate_column("by", "user_id")
        IdentifierValidator.validate_column("col", "_private")
        IdentifierValidator.validate_column("col", "CamelCase")

    def test_empty_string_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            IdentifierValidator.validate_column("col", "")

    def test_non_string_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            IdentifierValidator.validate_column("col", 42)  # type: ignore[arg-type]

    def test_leading_digit_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            IdentifierValidator.validate_column("col", "1bad")

    def test_space_in_name_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            IdentifierValidator.validate_column("col", "my col")

    def test_hyphen_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            IdentifierValidator.validate_column("col", "my-col")

    def test_dot_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            IdentifierValidator.validate_column("col", "a.b")

    def test_error_contains_label(self) -> None:
        try:
            IdentifierValidator.validate_column("left_on", "bad name")
        except ValueError as e:
            self.assertIn("left_on", str(e))


class TestIdentifierValidatorValidateColumns(unittest.TestCase):
    def test_valid_list(self) -> None:
        IdentifierValidator.validate_columns("cols", ["a", "b", "c"])

    def test_empty_list_raises(self) -> None:
        with self.assertRaises(ValueError):
            IdentifierValidator.validate_columns("cols", [])

    def test_string_not_a_sequence_raises(self) -> None:
        with self.assertRaises(TypeError):
            IdentifierValidator.validate_columns("cols", "abc")

    def test_invalid_entry_raises(self) -> None:
        with self.assertRaises(ValueError):
            IdentifierValidator.validate_columns("cols", ["good", "bad col"])

    def test_error_includes_index(self) -> None:
        try:
            IdentifierValidator.validate_columns("cols", ["ok", "bad name"])
        except ValueError as e:
            self.assertIn("[1]", str(e))
