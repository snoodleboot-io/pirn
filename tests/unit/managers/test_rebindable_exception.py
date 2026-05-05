from __future__ import annotations

import unittest

from pirn.managers.rebindable_exception import RebindableException


class TestRebindableException(unittest.TestCase):
    def test_is_exception(self):
        self.assertTrue(issubclass(RebindableException, Exception))

    def test_fields_stored(self):
        exc = RebindableException("ValueError", "bad", "Traceback...")
        self.assertEqual(exc.original_exc_type, "ValueError")
        self.assertEqual(exc.original_traceback_text, "Traceback...")

    def test_message_is_str_exc(self):
        exc = RebindableException("ValueError", "bad value", "tb")
        self.assertEqual(str(exc), "bad value")

    def test_raise_and_catch(self):
        with self.assertRaises(RebindableException) as ctx:
            raise RebindableException("TypeError", "type error", "tb text")
        self.assertEqual(ctx.exception.original_exc_type, "TypeError")

    def test_catch_as_base_exception(self):
        with self.assertRaises(Exception):
            raise RebindableException("E", "m", "t")
