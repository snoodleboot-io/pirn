from __future__ import annotations

import unittest

from pirn.exceptions.pirn_error import PirnError
from pirn.exceptions.tapestry_error import TapestryError


class TestTapestryError(unittest.TestCase):
    def test_is_pirn_error(self):
        self.assertTrue(issubclass(TapestryError, PirnError))

    def test_raise_and_catch_as_pirn_error(self):
        with self.assertRaises(PirnError):
            raise TapestryError("empty run")

    def test_message_preserved(self):
        err = TapestryError("unknown emitter")
        self.assertEqual(str(err), "unknown emitter")

    def test_raise_and_catch_specific(self):
        with self.assertRaises(TapestryError):
            raise TapestryError("x")
