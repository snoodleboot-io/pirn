from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped
from pirn.exceptions.pirn_error import PirnError
from pirn.exceptions.result_unwrap_error import ResultUnwrapError
from pirn.managers.exception_record import ExceptionRecord


class TestResultUnwrapError(unittest.TestCase):
    def test_is_pirn_error(self) -> None:
        self.assertTrue(issubclass(ResultUnwrapError, PirnError))

    def test_is_runtime_error_so_existing_handlers_still_catch_it(self) -> None:
        self.assertTrue(issubclass(ResultUnwrapError, RuntimeError))

    def test_unwrapping_an_err_raises_it(self) -> None:
        err = Err(record=ExceptionRecord.for_knot("k", ValueError("boom")))
        with self.assertRaises(ResultUnwrapError) as ctx:
            err.unwrap()
        self.assertIn("boom", str(ctx.exception))

    def test_unwrapping_a_skipped_raises_it(self) -> None:
        with self.assertRaises(ResultUnwrapError) as ctx:
            Skipped(reason="gate_closed").unwrap()
        self.assertIn("gate_closed", str(ctx.exception))

    def test_unwrapping_an_ok_returns_the_value(self) -> None:
        self.assertEqual(Ok(value=7).unwrap(), 7)
