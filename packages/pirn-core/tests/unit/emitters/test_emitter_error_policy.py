"""Unit tests for EmitterErrorPolicy."""

from __future__ import annotations

import unittest

from pirn.emitters.emitter_error_policy import EmitterErrorPolicy


class TestEmitterErrorPolicy(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(EmitterErrorPolicy.WARN, "warn")
        self.assertEqual(EmitterErrorPolicy.IGNORE, "ignore")
        self.assertEqual(EmitterErrorPolicy.RAISE, "raise")

    def test_is_str_enum(self) -> None:
        self.assertIsInstance(EmitterErrorPolicy.WARN, str)

    def test_membership(self) -> None:
        values = set(EmitterErrorPolicy)
        self.assertIn(EmitterErrorPolicy.WARN, values)
        self.assertIn(EmitterErrorPolicy.IGNORE, values)
        self.assertIn(EmitterErrorPolicy.RAISE, values)
