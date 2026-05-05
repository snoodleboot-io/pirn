from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.managers.exception_record import ExceptionRecord


class TestExceptionRecord(unittest.TestCase):
    def _make(self, **kwargs) -> ExceptionRecord:
        defaults = dict(
            run_id="run-1",
            knot_id="knot-a",
            exc_type="ValueError",
            message="bad value",
            traceback_text="Traceback...",
        )
        defaults.update(kwargs)
        return ExceptionRecord(**defaults)

    def test_fields_stored(self):
        rec = self._make()
        self.assertEqual(rec.run_id, "run-1")
        self.assertEqual(rec.knot_id, "knot-a")
        self.assertEqual(rec.exc_type, "ValueError")
        self.assertEqual(rec.message, "bad value")

    def test_id_generated_with_prefix(self):
        rec = self._make()
        self.assertTrue(rec.id.startswith("exc-"))

    def test_ids_unique(self):
        r1 = self._make()
        r2 = self._make()
        self.assertNotEqual(r1.id, r2.id)

    def test_occurred_at_defaults_to_utc_now(self):
        before = datetime.now(UTC)
        rec = self._make()
        after = datetime.now(UTC)
        self.assertGreaterEqual(rec.occurred_at, before)
        self.assertLessEqual(rec.occurred_at, after)

    def test_frozen(self):
        rec = self._make()
        with self.assertRaises(Exception):
            rec.run_id = "other"  # type: ignore[misc]

    def test_for_knot_sets_unbound_run_id(self):
        exc = ValueError("oops")
        rec = ExceptionRecord.for_knot("knot-x", exc)
        self.assertEqual(rec.run_id, "<unbound>")
        self.assertEqual(rec.knot_id, "knot-x")
        self.assertEqual(rec.exc_type, "ValueError")
        self.assertEqual(rec.message, "oops")

    def test_for_knot_captures_traceback(self):
        try:
            raise RuntimeError("from try")
        except RuntimeError as exc:
            rec = ExceptionRecord.for_knot("k", exc)
        self.assertIn("RuntimeError", rec.traceback_text)

    def test_for_knot_no_traceback_when_no_frames(self):
        exc = KeyError("missing")
        rec = ExceptionRecord.for_knot("k", exc)
        self.assertIsInstance(rec.traceback_text, str)
