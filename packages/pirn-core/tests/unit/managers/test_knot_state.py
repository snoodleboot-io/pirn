from __future__ import annotations

import unittest

from pirn.managers.knot_state import KnotState


class TestKnotState(unittest.TestCase):
    def test_all_values_exist(self):
        states = {s.value for s in KnotState}
        self.assertEqual(states, {"pending", "running", "succeeded", "failed", "skipped"})

    def test_is_str(self):
        self.assertIsInstance(KnotState.PENDING, str)
        self.assertEqual(KnotState.PENDING, "pending")

    def test_str_comparison(self):
        self.assertEqual(KnotState.RUNNING, "running")
        self.assertEqual(KnotState.SUCCEEDED, "succeeded")
        self.assertEqual(KnotState.FAILED, "failed")
        self.assertEqual(KnotState.SKIPPED, "skipped")

    def test_from_value(self):
        self.assertIs(KnotState("pending"), KnotState.PENDING)
        self.assertIs(KnotState("failed"), KnotState.FAILED)
