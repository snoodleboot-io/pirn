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
        with self.assertRaises(Exception):
            raise RebindableError("E", "m", "t")
