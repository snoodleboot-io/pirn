from __future__ import annotations

import unittest

from pirn.exceptions.data_integrity_error import DataIntegrityError
from pirn.exceptions.pirn_error import PirnError


class TestDataIntegrityError(unittest.TestCase):
    def test_is_pirn_error(self):
        self.assertTrue(issubclass(DataIntegrityError, PirnError))

    def test_raise_and_catch_as_pirn_error(self):
        with self.assertRaises(PirnError):
            raise DataIntegrityError("bad hmac")

    def test_message_preserved(self):
        err = DataIntegrityError("signature mismatch")
        self.assertEqual(str(err), "signature mismatch")

    def test_raise_and_catch_specific(self):
        with self.assertRaises(DataIntegrityError):
            raise DataIntegrityError("x")
