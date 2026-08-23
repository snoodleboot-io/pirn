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
        # Deliberate blind-Exception assert: this test's whole point is that a
        # PirnError is catchable via the builtin Exception base. Narrowing to
        # PirnError would duplicate test_raise_and_catch and drop that coverage;
        # the raise is inline, so there is no wrong-exception false-green risk.
        with self.assertRaises(Exception):  # noqa: B017
            raise PirnError("caught as base")

    def test_empty_message(self):
        err = PirnError()
        self.assertEqual(str(err), "")
