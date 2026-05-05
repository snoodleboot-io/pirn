from __future__ import annotations

import unittest

from pirn.exceptions.duplicate_knot_error import DuplicateKnotError
from pirn.exceptions.pirn_error import PirnError


class TestDuplicateKnotError(unittest.TestCase):
    def test_is_pirn_error(self):
        self.assertTrue(issubclass(DuplicateKnotError, PirnError))

    def test_raise_and_catch_as_pirn_error(self):
        with self.assertRaises(PirnError):
            raise DuplicateKnotError("my-knot")

    def test_message_preserved(self):
        err = DuplicateKnotError("knot already registered")
        self.assertEqual(str(err), "knot already registered")

    def test_raise_and_catch_specific(self):
        with self.assertRaises(DuplicateKnotError):
            raise DuplicateKnotError("x")
