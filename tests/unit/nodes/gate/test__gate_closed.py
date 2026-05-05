"""Unit tests for _GateClosed."""

from __future__ import annotations

import unittest

from pirn.nodes.gate._gate_closed import _GateClosed


class TestGateClosed(unittest.TestCase):
    def test_is_exception(self) -> None:
        self.assertTrue(issubclass(_GateClosed, Exception))

    def test_can_be_raised_and_caught(self) -> None:
        with self.assertRaises(_GateClosed):
            raise _GateClosed
