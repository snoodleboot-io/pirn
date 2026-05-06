from __future__ import annotations

import unittest

from pirn.core.error_policy import ErrorPolicy


class TestErrorPolicy(unittest.TestCase):
    def test_all_members_exist(self) -> None:
        self.assertIn("SKIP_IF_PARENT_FAILED", ErrorPolicy.__members__)
        self.assertIn("RECEIVE_ERRORS", ErrorPolicy.__members__)
        self.assertIn("REQUIRE_ALL_PARENTS", ErrorPolicy.__members__)

    def test_string_values(self) -> None:
        self.assertEqual(ErrorPolicy.SKIP_IF_PARENT_FAILED, "skip_if_parent_failed")
        self.assertEqual(ErrorPolicy.RECEIVE_ERRORS, "receive_errors")
        self.assertEqual(ErrorPolicy.REQUIRE_ALL_PARENTS, "require_all_parents")

    def test_is_str_enum(self) -> None:
        self.assertIsInstance(ErrorPolicy.SKIP_IF_PARENT_FAILED, str)

    def test_lookup_by_value(self) -> None:
        self.assertIs(ErrorPolicy("skip_if_parent_failed"), ErrorPolicy.SKIP_IF_PARENT_FAILED)

    def test_default_in_knot_config(self) -> None:
        from pirn.core.knot_config import KnotConfig

        cfg = KnotConfig(id="k")
        self.assertIs(cfg.error_policy, ErrorPolicy.SKIP_IF_PARENT_FAILED)
