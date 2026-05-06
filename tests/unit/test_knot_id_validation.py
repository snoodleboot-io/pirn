"""Tests for KnotConfig id character validation (security finding L-9)."""

from __future__ import annotations
import unittest

from pydantic import ValidationError

from pirn.core.knot_config import KnotConfig


def make_config(id: str) -> KnotConfig:
    return KnotConfig(id=id)


_VALID_IDS = [
    "my-knot",
    "etl.load.users",
    "param:x",
    "knot_123",
    "a",
    "A-B.C:D_1",
]


class TestKnotIdValidation(unittest.TestCase):
    def test_valid_ids(self) -> None:
        for valid_id in _VALID_IDS:
            with self.subTest(valid_id=valid_id):
                config = make_config(valid_id)
                assert config.id == valid_id

    def test_invalid_null_byte(self) -> None:
        with self.assertRaises(ValidationError):
            make_config("knot\x00id")

    def test_invalid_newline(self) -> None:
        with self.assertRaises(ValidationError):
            make_config("knot\nid")

    def test_invalid_path_separator(self) -> None:
        with self.assertRaises(ValidationError):
            make_config("knot/id")

    def test_invalid_space(self) -> None:
        with self.assertRaises(ValidationError):
            make_config("knot id")

    def test_invalid_ansi_escape(self) -> None:
        with self.assertRaises(ValidationError):
            make_config("knot\x1b[31mid")

    def test_invalid_too_long(self) -> None:
        with self.assertRaises(ValidationError):
            make_config("a" * 257)

    def test_empty_string_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            make_config("")
