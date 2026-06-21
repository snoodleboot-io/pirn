from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord


def _make_record() -> ExceptionRecord:
    return ExceptionRecord(
        run_id="run-1",
        knot_id="k",
        exc_type="ValueError",
        message="bad",
        traceback_text="tb",
    )


class TestResult(unittest.TestCase):
    def test_ok_is_result(self):
        ok: Result = Ok(value=1)
        self.assertIsInstance(ok, Ok)

    def test_err_is_result(self):
        err: Result = Err(record=_make_record())
        self.assertIsInstance(err, Err)

    def test_skipped_is_result(self):
        s: Result = Skipped()
        self.assertIsInstance(s, Skipped)

    def test_all_exported(self):
        from pirn.core.result import __all__
        self.assertIn("Ok", __all__)
        self.assertIn("Err", __all__)
        self.assertIn("Skipped", __all__)
        self.assertIn("Result", __all__)

    def test_discriminate_by_is_ok(self):
        results: list[Result] = [Ok(value=1), Err(record=_make_record()), Skipped()]
        ok_results = [r for r in results if r.is_ok]
        self.assertEqual(len(ok_results), 1)

    def test_discriminate_by_is_err(self):
        results: list[Result] = [Ok(value=1), Err(record=_make_record()), Skipped()]
        err_results = [r for r in results if r.is_err]
        self.assertEqual(len(err_results), 1)

    def test_discriminate_by_is_skipped(self):
        results: list[Result] = [Ok(value=1), Err(record=_make_record()), Skipped()]
        skip_results = [r for r in results if r.is_skipped]
        self.assertEqual(len(skip_results), 1)
