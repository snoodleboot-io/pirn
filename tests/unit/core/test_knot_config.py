from __future__ import annotations

import unittest

from pydantic import ValidationError

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot_config import KnotConfig


class TestKnotConfig(unittest.TestCase):
    def test_minimal_construction(self) -> None:
        cfg = KnotConfig(id="my-knot")
        self.assertEqual(cfg.id, "my-knot")
        self.assertTrue(cfg.validate_io)
        self.assertEqual(cfg.error_policy, ErrorPolicy.SKIP_IF_PARENT_FAILED)
        self.assertIsNone(cfg.description)
        self.assertEqual(cfg.tags, ())

    def test_id_required(self) -> None:
        with self.assertRaises(ValidationError):
            KnotConfig()

    def test_id_empty_string_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            KnotConfig(id="")

    def test_id_valid_characters(self) -> None:
        for valid_id in ["abc", "ABC", "a1_b2", "a-b", "a.b", "a:b", "x" * 256]:
            with self.subTest(id=valid_id):
                cfg = KnotConfig(id=valid_id)
                self.assertEqual(cfg.id, valid_id)

    def test_id_invalid_characters(self) -> None:
        for bad_id in ["a b", "a/b", "a\nb", "a\x00b"]:
            with self.subTest(id=bad_id):
                with self.assertRaises(ValidationError):
                    KnotConfig(id=bad_id)

    def test_id_exceeds_max_length(self) -> None:
        with self.assertRaises(ValidationError):
            KnotConfig(id="x" * 257)

    def test_custom_error_policy(self) -> None:
        cfg = KnotConfig(id="k", error_policy=ErrorPolicy.RECEIVE_ERRORS)
        self.assertEqual(cfg.error_policy, ErrorPolicy.RECEIVE_ERRORS)

    def test_description_and_tags(self) -> None:
        cfg = KnotConfig(id="k", description="hello", tags=("a", "b"))
        self.assertEqual(cfg.description, "hello")
        self.assertEqual(cfg.tags, ("a", "b"))

    def test_validate_io_false(self) -> None:
        cfg = KnotConfig(id="k", validate_io=False)
        self.assertFalse(cfg.validate_io)

    def test_frozen(self) -> None:
        cfg = KnotConfig(id="k")
        with self.assertRaises(Exception):
            cfg.id = "other"

    def test_extra_fields_forbidden(self) -> None:
        with self.assertRaises(ValidationError):
            KnotConfig(id="k", unknown_field="x")
