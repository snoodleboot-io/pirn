"""Unit tests for _GateClosedError."""

from __future__ import annotations

import unittest

from pirn.nodes.gate._gate_closed import _GateClosedError


class TestGateClosed(unittest.TestCase):
    def test_is_exception(self) -> None:
        self.assertTrue(issubclass(_GateClosedError, Exception))

    def test_can_be_raised_and_caught(self) -> None:
        with self.assertRaises(_GateClosedError):
            raise _GateClosedError
