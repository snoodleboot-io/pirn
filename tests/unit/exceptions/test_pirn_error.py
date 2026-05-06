from __future__ import annotations

import unittest

from pirn.exceptions.pirn_error import PirnError


class TestPirnError(unittest.TestCase):
    def test_is_exception(self):
        self.assertTrue(issubclass(PirnError, Exception))

    def test_raise_and_catch(self):
        with self.assertRaises(PirnError):
            raise PirnError("boom")

    def test_message_preserved(self):
        err = PirnError("test message")
        self.assertEqual(str(err), "test message")

    def test_catch_as_exception(self):
        with self.assertRaises(Exception):
            raise PirnError("caught as base")

    def test_empty_message(self):
        err = PirnError()
        self.assertEqual(str(err), "")
