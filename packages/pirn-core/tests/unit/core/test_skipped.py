from __future__ import annotations

import unittest

from pirn.core.skipped import Skipped


class TestSkipped(unittest.TestCase):
    def test_is_ok_false(self):
        self.assertFalse(Skipped().is_ok)

    def test_is_err_false(self):
        self.assertFalse(Skipped().is_err)

    def test_is_skipped_true(self):
        self.assertTrue(Skipped().is_skipped)

    def test_default_reason(self):
        s = Skipped()
        self.assertEqual(s.reason, "skipped")

    def test_custom_reason(self):
        s = Skipped(reason="branch not taken")
        self.assertEqual(s.reason, "branch not taken")

    def test_default_detail_empty(self):
        s = Skipped()
        self.assertEqual(s.detail, {})

    def test_custom_detail(self):
        s = Skipped(detail={"gate": "closed"})
        self.assertEqual(s.detail["gate"], "closed")

    def test_unwrap_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            Skipped(reason="no run").unwrap()
        self.assertIn("Skipped", str(ctx.exception))

    def test_frozen(self):
        s = Skipped()
        with self.assertRaises(Exception):
            s.reason = "other"  # type: ignore[misc]
