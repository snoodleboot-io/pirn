from __future__ import annotations

import unittest

from pirn.exceptions.pirn_error import PirnError
from pirn.exceptions.unbound_parameter_error import UnboundParameterError


class TestUnboundParameterError(unittest.TestCase):
    def test_is_pirn_error(self):
        self.assertTrue(issubclass(UnboundParameterError, PirnError))

    def test_raise_and_catch_as_pirn_error(self):
        with self.assertRaises(PirnError):
            raise UnboundParameterError("param 'x' has no value")

    def test_message_preserved(self):
        err = UnboundParameterError("param 'threshold' has no value bound and no default")
        self.assertIn("threshold", str(err))

    def test_raise_and_catch_specific(self):
        with self.assertRaises(UnboundParameterError):
            raise UnboundParameterError("x")
