from __future__ import annotations

import unittest

from pirn.managers.knot_state import KnotState
from pirn.managers.status_event import StatusEvent
from pirn.managers.status_manager import StatusManager


class TestStatusManager(unittest.TestCase):
    def setUp(self):
        self.mgr = StatusManager(run_id="run-1")

    def test_get_unknown_knot_returns_pending(self):
        self.assertEqual(self.mgr.get("unknown"), KnotState.PENDING)

    def test_transition_stores_state(self):
        self.mgr.transition("k1", KnotState.RUNNING)
        self.assertEqual(self.mgr.get("k1"), KnotState.RUNNING)

    def test_transition_returns_event(self):
        ev = self.mgr.transition("k1", KnotState.SUCCEEDED)
        self.assertIsInstance(ev, StatusEvent)
        self.assertEqual(ev.run_id, "run-1")
        self.assertEqual(ev.knot_id, "k1")
        self.assertEqual(ev.state, KnotState.SUCCEEDED)

    def test_transition_with_detail(self):
        ev = self.mgr.transition("k1", KnotState.FAILED, detail="oops")
        self.assertEqual(ev.detail, "oops")

    def test_events_accumulate(self):
        self.mgr.transition("k1", KnotState.RUNNING)
        self.mgr.transition("k1", KnotState.SUCCEEDED)
        self.assertEqual(len(self.mgr.events()), 2)

    def test_events_returns_copy(self):
        self.mgr.transition("k1", KnotState.RUNNING)
        evs = self.mgr.events()
        evs.clear()
        self.assertEqual(len(self.mgr.events()), 1)

    def test_snapshot(self):
        self.mgr.transition("k1", KnotState.RUNNING)
        self.mgr.transition("k2", KnotState.SUCCEEDED)
        snap = self.mgr.snapshot()
        self.assertEqual(snap["k1"], KnotState.RUNNING)
        self.assertEqual(snap["k2"], KnotState.SUCCEEDED)

    def test_snapshot_is_copy(self):
        self.mgr.transition("k1", KnotState.RUNNING)
        snap = self.mgr.snapshot()
        snap["k1"] = KnotState.FAILED
        self.assertEqual(self.mgr.get("k1"), KnotState.RUNNING)

    def test_subscriber_called_on_transition(self):
        received = []
        self.mgr.subscribe(received.append)
        self.mgr.transition("k1", KnotState.RUNNING)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].state, KnotState.RUNNING)

    def test_failing_subscriber_does_not_crash(self):
        def bad_sub(_: StatusEvent) -> None:
            raise RuntimeError("subscriber error")

        self.mgr.subscribe(bad_sub)
        self.mgr.transition("k1", KnotState.RUNNING)
        self.assertEqual(self.mgr.get("k1"), KnotState.RUNNING)
