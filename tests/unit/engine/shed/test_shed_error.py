"""Unit tests for ShedError."""

from __future__ import annotations

import unittest

from pirn.engine.shed.shed_error import ShedError


class TestShedError(unittest.TestCase):
    def test_is_exception(self) -> None:
        self.assertTrue(issubclass(ShedError, Exception))

    def test_message_preserved(self) -> None:
        err = ShedError("cycle detected")
        self.assertIn("cycle detected", str(err))

    def test_can_be_raised_and_caught(self) -> None:
        with self.assertRaises(ShedError):
            raise ShedError("id collision")
