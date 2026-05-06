from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.managers.exception_record import ExceptionRecord


def _make_record(**kwargs) -> ExceptionRecord:
    defaults = dict(
        run_id="run-1",
        knot_id="k",
        exc_type="ValueError",
        message="bad",
        traceback_text="tb",
    )
    defaults.update(kwargs)
    return ExceptionRecord(**defaults)


class TestErr(unittest.TestCase):
    def test_is_ok_false(self):
        err = Err(record=_make_record())
        self.assertFalse(err.is_ok)

    def test_is_err_true(self):
        err = Err(record=_make_record())
        self.assertTrue(err.is_err)

    def test_is_skipped_false(self):
        err = Err(record=_make_record())
        self.assertFalse(err.is_skipped)

    def test_record_stored(self):
        rec = _make_record(message="specific message")
        err = Err(record=rec)
        self.assertIs(err.record, rec)

    def test_unwrap_raises_runtime_error(self):
        err = Err(record=_make_record())
        with self.assertRaises(RuntimeError) as ctx:
            err.unwrap()
        self.assertIn("Err", str(ctx.exception))

    def test_frozen(self):
        err = Err(record=_make_record())
        with self.assertRaises(Exception):
            err.record = _make_record()  # type: ignore[misc]
