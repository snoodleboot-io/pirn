from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.managers.knot_state import KnotState
from pirn.managers.status_event import StatusEvent


class TestStatusEvent(unittest.TestCase):
    def _make(self, **kwargs) -> StatusEvent:
        defaults = dict(run_id="run-1", knot_id="knot-a", state=KnotState.RUNNING)
        defaults.update(kwargs)
        return StatusEvent(**defaults)

    def test_fields_stored(self):
        ev = self._make()
        self.assertEqual(ev.run_id, "run-1")
        self.assertEqual(ev.knot_id, "knot-a")
        self.assertEqual(ev.state, KnotState.RUNNING)

    def test_detail_defaults_to_none(self):
        ev = self._make()
        self.assertIsNone(ev.detail)

    def test_detail_stored(self):
        ev = self._make(detail="some info")
        self.assertEqual(ev.detail, "some info")

    def test_occurred_at_defaults_to_utc(self):
        before = datetime.now(UTC)
        ev = self._make()
        after = datetime.now(UTC)
        self.assertGreaterEqual(ev.occurred_at, before)
        self.assertLessEqual(ev.occurred_at, after)

    def test_frozen(self):
        ev = self._make()
        with self.assertRaises(Exception):
            ev.run_id = "other"  # type: ignore[misc]
