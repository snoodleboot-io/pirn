"""``ReadyQueue.waiting_in`` — per-group queue depth for admission feedback (WS0)."""

from __future__ import annotations

import unittest

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.engine.admission.limited_admission_gate import LimitedAdmissionGate
from pirn.engine.scheduling.ready_queue import ReadyQueue
from pirn.engine.shed.shed import Shed


def _shed(*knots: Parameter) -> Shed:
    return Shed.from_terminals(list(knots))


class TestWaitingIn(unittest.TestCase):
    def test_counts_queued_knots_per_group(self) -> None:
        # Arrange
        queue = ReadyQueue()
        queue.push_batch([(0, "a", "api"), (1, "b", "api"), (2, "c", None)])

        # Assert
        self.assertEqual(queue.waiting_in("api"), 2)
        self.assertEqual(queue.waiting_in(None), 1)
        self.assertEqual(queue.waiting_in("other"), 0)

    def test_decrements_as_knots_are_admitted(self) -> None:
        # Arrange
        a = Parameter("a", int, default=1, _config=KnotConfig(id="a", concurrency_group="api"))
        b = Parameter("b", int, default=1, _config=KnotConfig(id="b", concurrency_group="api"))
        shed = _shed(a, b)
        queue = ReadyQueue()
        queue.push_batch([(0, "a", "api"), (1, "b", "api")])
        gate = LimitedAdmissionGate(ConcurrencyLimits(groups={"api": 1}))

        # Act
        admitted = queue.pop_admissible(gate, shed)

        # Assert
        assert admitted is not None
        self.assertEqual(admitted[0], "a")
        self.assertEqual(queue.waiting_in("api"), 1)
        self.assertIsNone(queue.pop_admissible(gate, shed))
        self.assertEqual(queue.waiting_in("api"), 1)

    def test_empty_queue_reports_zero(self) -> None:
        self.assertEqual(ReadyQueue().waiting_in(None), 0)
