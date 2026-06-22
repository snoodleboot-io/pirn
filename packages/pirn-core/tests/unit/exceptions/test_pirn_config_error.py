from __future__ import annotations

import unittest

from pirn.exceptions.pirn_config_error import PirnConfigError
from pirn.exceptions.pirn_error import PirnError


class TestPirnConfigError(unittest.TestCase):
    def test_is_pirn_error(self):
        self.assertTrue(issubclass(PirnConfigError, PirnError))

    def test_raise_and_catch_as_pirn_error(self):
        with self.assertRaises(PirnError):
            raise PirnConfigError("missing key")

    def test_message_preserved(self):
        err = PirnConfigError("config value out of range")
        self.assertEqual(str(err), "config value out of range")

    def test_raise_and_catch_specific(self):
        with self.assertRaises(PirnConfigError):
            raise PirnConfigError("x")
