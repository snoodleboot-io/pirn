from __future__ import annotations

import unittest

from pydantic import ValidationError

from pirn.core.content_hasher import ContentHasher
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
        with self.assertRaises(ValidationError):
            cfg.id = "other"

    def test_extra_fields_forbidden(self) -> None:
        with self.assertRaises(ValidationError):
            KnotConfig(id="k", unknown_field="x")


class TestKnotConfigConcurrencyGroup(unittest.TestCase):
    """``concurrency_group`` names the admission group a knot belongs to (PIR-841).

    It is scheduling policy, not identity, so it must never reach the config
    dump that ``knot_config_hash`` is computed from: adding it would change
    every hash and break replay of every existing recording.
    """

    # Hashes computed on main (6a6dd966), before the field existed.
    golden_minimal = "sha256:20d4f1367644ce1dcfb00c4d68a5595ad4cf695df734a50a4339e8c69937b62a"
    golden_full = "sha256:dffa07aaa0568ebac148c78c33e310dd58d960ed405bc50aaee655e999151ec0"

    def test_defaults_to_no_group(self) -> None:
        self.assertIsNone(KnotConfig(id="k").concurrency_group)

    def test_stores_the_group(self) -> None:
        self.assertEqual(KnotConfig(id="k", concurrency_group="api").concurrency_group, "api")

    def test_is_excluded_from_the_config_dump(self) -> None:
        # Arrange
        cfg = KnotConfig(id="k", concurrency_group="api")

        # Act
        dumped = cfg.model_dump(mode="json")

        # Assert
        self.assertNotIn("concurrency_group", dumped)
        self.assertNotIn("concurrency_group", cfg.model_dump_json())

    def test_config_hash_is_unchanged_from_before_the_field_existed(self) -> None:
        # Arrange
        minimal = KnotConfig(id="k")
        full = KnotConfig(
            id="llm0",
            error_policy=ErrorPolicy.RECEIVE_ERRORS,
            tags=("api",),
            description="call",
        )

        # Act / Assert
        self.assertEqual(ContentHasher.hash(minimal.model_dump(mode="json")), self.golden_minimal)
        self.assertEqual(ContentHasher.hash(full.model_dump(mode="json")), self.golden_full)

    def test_same_knot_hashes_identically_with_and_without_a_group(self) -> None:
        # Arrange
        grouped = KnotConfig(id="k", concurrency_group="api")

        # Act
        digest = ContentHasher.hash(grouped.model_dump(mode="json"))

        # Assert
        self.assertEqual(digest, self.golden_minimal)

    def test_rejects_group_names_outside_the_knot_id_charset(self) -> None:
        for bad in ["", "a b", "a/b", "a\x00b", "x" * 257]:
            with self.subTest(group=bad), self.assertRaises(ValidationError):
                KnotConfig(id="k", concurrency_group=bad)
