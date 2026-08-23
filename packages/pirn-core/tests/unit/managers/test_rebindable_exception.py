from __future__ import annotations

import unittest

from pirn.managers.rebindable_exception import RebindableError


class TestRebindableError(unittest.TestCase):
    def test_is_exception(self):
        self.assertTrue(issubclass(RebindableError, Exception))

    def test_fields_stored(self):
        exc = RebindableError("ValueError", "bad", "Traceback...")
        self.assertEqual(exc.original_exc_type, "ValueError")
        self.assertEqual(exc.original_traceback_text, "Traceback...")

    def test_message_is_str_exc(self):
        exc = RebindableError("ValueError", "bad value", "tb")
        self.assertEqual(str(exc), "bad value")

    def test_raise_and_catch(self):
        with self.assertRaises(RebindableError) as ctx:
            raise RebindableError("TypeError", "type error", "tb text")
        self.assertEqual(ctx.exception.original_exc_type, "TypeError")

    def test_catch_as_base_exception(self):
        # Deliberate blind-Exception assert: this test's whole point is that a
        # RebindableError is catchable via the builtin Exception base. Narrowing
        # to RebindableError would duplicate test_raise_and_catch and drop that
        # coverage; the raise is inline, so there is no false-green risk.
        with self.assertRaises(Exception):  # noqa: B017
            raise RebindableError("E", "m", "t")
