from __future__ import annotations

import unittest

from pirn.exceptions.invalid_branch_error import InvalidBranchError
from pirn.exceptions.pirn_error import PirnError


class TestInvalidBranchError(unittest.TestCase):
    def test_is_pirn_error(self):
        self.assertTrue(issubclass(InvalidBranchError, PirnError))

    def test_raise_and_catch_as_pirn_error(self):
        with self.assertRaises(PirnError):
            raise InvalidBranchError("branch_x")

    def test_message_preserved(self):
        err = InvalidBranchError("undeclared branch: foo")
        self.assertEqual(str(err), "undeclared branch: foo")

    def test_raise_and_catch_specific(self):
        with self.assertRaises(InvalidBranchError):
            raise InvalidBranchError("x")
