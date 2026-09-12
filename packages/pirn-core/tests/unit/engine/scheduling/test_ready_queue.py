"""Unit tests for ReadyQueue."""

from __future__ import annotations

import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.engine.admission.admission_gate import AdmissionGate
from pirn.engine.admission.admission_ticket import AdmissionTicket
from pirn.engine.admission.unbounded_admission_gate import UnboundedAdmissionGate
from pirn.engine.scheduling.ready_queue import ReadyQueue
from pirn.engine.shed.shed import Shed


class _RefuseIds(AdmissionGate):
    """Test double: refuses the named knots, admits the rest."""

    def __init__(self, refused: set[str]) -> None:
        self.refused = refused
        self.offered: list[str] = []
        self.offered_knots: list[Knot] = []

    def try_admit(self, knot: Knot) -> AdmissionTicket | None:
        self.offered.append(knot.knot_id)
        self.offered_knots.append(knot)
        if knot.knot_id in self.refused:
            return None
        return AdmissionTicket(knot_id=knot.knot_id)


def _shed(*knot_ids: str) -> Shed:
    return Shed.from_terminals(
        [Parameter("x", int, default=1, _config=KnotConfig(id=kid)) for kid in knot_ids]
    )


def _drain(queue: ReadyQueue, gate: AdmissionGate, shed: Shed) -> list[str]:
    popped: list[str] = []
    while (admitted := queue.pop_admissible(gate, shed)) is not None:
        popped.append(admitted[0])
    return popped


class TestReadyQueueOrdering(unittest.TestCase):
    def test_empty_queue_admits_nothing(self) -> None:
        # Arrange
        queue = ReadyQueue()

        # Act
        admitted = queue.pop_admissible(UnboundedAdmissionGate(), _shed("a"))

        # Assert
        self.assertIsNone(admitted)
        self.assertEqual(len(queue), 0)
        self.assertFalse(queue)

    def test_orders_a_batch_by_topological_index(self) -> None:
        # Arrange
        queue = ReadyQueue()
        shed = _shed("a", "b", "c")
        queue.push_batch([(2, "c"), (0, "a"), (1, "b")])

        # Act
        popped = _drain(queue, UnboundedAdmissionGate(), shed)

        # Assert
        self.assertEqual(popped, ["a", "b", "c"])

    def test_an_earlier_batch_is_served_before_a_later_one(self) -> None:
        # Arrange: "z" became ready first despite its larger topo index.
        queue = ReadyQueue()
        shed = _shed("a", "z")
        queue.push_batch([(9, "z")])
        queue.push_batch([(0, "a")])

        # Act
        popped = _drain(queue, UnboundedAdmissionGate(), shed)

        # Assert
        self.assertEqual(popped, ["z", "a"])

    def test_an_empty_batch_does_not_reorder_later_batches(self) -> None:
        # Arrange
        queue = ReadyQueue()
        shed = _shed("a", "b")
        queue.push_batch([(1, "b")])
        queue.push_batch([])
        queue.push_batch([(0, "a")])

        # Act
        popped = _drain(queue, UnboundedAdmissionGate(), shed)

        # Assert
        self.assertEqual(popped, ["b", "a"])

    def test_admission_returns_the_gate_ticket(self) -> None:
        # Arrange
        queue = ReadyQueue()
        queue.push_batch([(0, "a")])

        # Act
        admitted = queue.pop_admissible(UnboundedAdmissionGate(), _shed("a"))

        # Assert
        self.assertEqual(admitted, ("a", AdmissionTicket(knot_id="a")))


class TestReadyQueueRefusal(unittest.TestCase):
    def test_refused_head_stays_queued(self) -> None:
        # Arrange
        queue = ReadyQueue()
        shed = _shed("a", "b")
        queue.push_batch([(0, "a"), (1, "b")])
        gate = _RefuseIds({"a"})

        # Act
        admitted = queue.pop_admissible(gate, shed)

        # Assert
        self.assertIsNone(admitted)
        self.assertEqual(len(queue), 2)
        self.assertEqual(gate.offered, ["a"])

    def test_refused_head_is_admitted_once_the_gate_allows(self) -> None:
        # Arrange
        queue = ReadyQueue()
        shed = _shed("a", "b")
        queue.push_batch([(0, "a"), (1, "b")])
        gate = _RefuseIds({"a"})
        queue.pop_admissible(gate, shed)
        gate.refused.clear()

        # Act
        popped = _drain(queue, gate, shed)

        # Assert
        self.assertEqual(popped, ["a", "b"])

    def test_offers_the_instance_currently_in_the_shed(self) -> None:
        # Arrange: the engine swaps shed entries (parameter binding) while a
        # knot is queued, so the queue must look the knot up at admission.
        queue = ReadyQueue()
        shed = _shed("a")
        queue.push_batch([(0, "a")])
        replacement = Parameter("x", int, default=2, _config=KnotConfig(id="a"))
        shed.knots["a"] = replacement
        gate = _RefuseIds(set())

        # Act
        queue.pop_admissible(gate, shed)

        # Assert
        self.assertIs(gate.offered_knots[0], replacement)
