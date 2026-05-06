from __future__ import annotations

import unittest

from pirn.managers.exception_manager import ExceptionManager
from pirn.managers.exception_record import ExceptionRecord
from pirn.managers.rebindable_exception import RebindableException


class TestExceptionManager(unittest.TestCase):
    def setUp(self):
        self.mgr = ExceptionManager(run_id="run-abc")

    def test_record_stores_exception(self):
        exc = ValueError("oops")
        rec = self.mgr.record("knot-1", exc)
        self.assertIsInstance(rec, ExceptionRecord)
        self.assertEqual(rec.run_id, "run-abc")
        self.assertEqual(rec.knot_id, "knot-1")
        self.assertEqual(rec.exc_type, "ValueError")
        self.assertEqual(rec.message, "oops")

    def test_has_failures_false_initially(self):
        self.assertFalse(self.mgr.has_failures())

    def test_has_failures_true_after_record(self):
        self.mgr.record("k", ValueError("x"))
        self.assertTrue(self.mgr.has_failures())

    def test_len(self):
        self.assertEqual(len(self.mgr), 0)
        self.mgr.record("k1", ValueError("a"))
        self.mgr.record("k2", RuntimeError("b"))
        self.assertEqual(len(self.mgr), 2)

    def test_report_returns_list(self):
        self.mgr.record("k", ValueError("x"))
        report = self.mgr.report()
        self.assertIsInstance(report, list)
        self.assertEqual(len(report), 1)

    def test_report_is_copy(self):
        self.mgr.record("k", ValueError("x"))
        r1 = self.mgr.report()
        r1.clear()
        self.assertEqual(len(self.mgr.report()), 1)

    def test_get_by_id(self):
        rec = self.mgr.record("k", ValueError("y"))
        fetched = self.mgr.get(rec.id)
        self.assertIs(fetched, rec)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.mgr.get("nonexistent"))

    def test_rebindable_preserves_original_type(self):
        rb = RebindableException("OriginalError", "original msg", "original tb")
        rec = self.mgr.record("k", rb)
        self.assertEqual(rec.exc_type, "OriginalError")
        self.assertEqual(rec.traceback_text, "original tb")
        self.assertEqual(rec.message, "original msg")

    def test_traceback_filter_applied(self):
        def mask(text: str) -> str:
            return text.replace("secret", "MASKED")

        mgr = ExceptionManager(run_id="run-1", traceback_filter=mask)
        exc = ValueError("secret value")
        rec = mgr.record("k", exc)
        self.assertNotIn("secret", rec.traceback_text)
