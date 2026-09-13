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
        queue.push_batch([(2, "c", None), (0, "a", None), (1, "b", None)])

        # Act
        popped = _drain(queue, UnboundedAdmissionGate(), shed)

        # Assert
        self.assertEqual(popped, ["a", "b", "c"])

    def test_an_earlier_batch_is_served_before_a_later_one(self) -> None:
        # Arrange: "z" became ready first despite its larger topo index.
        queue = ReadyQueue()
        shed = _shed("a", "z")
        queue.push_batch([(9, "z", None)])
        queue.push_batch([(0, "a", None)])

        # Act
        popped = _drain(queue, UnboundedAdmissionGate(), shed)

        # Assert
        self.assertEqual(popped, ["z", "a"])

    def test_an_empty_batch_does_not_reorder_later_batches(self) -> None:
        # Arrange
        queue = ReadyQueue()
        shed = _shed("a", "b")
        queue.push_batch([(1, "b", None)])
        queue.push_batch([])
        queue.push_batch([(0, "a", None)])

        # Act
        popped = _drain(queue, UnboundedAdmissionGate(), shed)

        # Assert
        self.assertEqual(popped, ["b", "a"])

    def test_admission_returns_the_gate_ticket(self) -> None:
        # Arrange
        queue = ReadyQueue()
        queue.push_batch([(0, "a", None)])

        # Act
        admitted = queue.pop_admissible(UnboundedAdmissionGate(), _shed("a"))

        # Assert
        self.assertEqual(admitted, ("a", AdmissionTicket(knot_id="a")))


class TestReadyQueueRefusal(unittest.TestCase):
    def test_refused_head_stays_queued(self) -> None:
        # Arrange
        queue = ReadyQueue()
        shed = _shed("a", "b")
        queue.push_batch([(0, "a", None), (1, "b", None)])
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
        queue.push_batch([(0, "a", None), (1, "b", None)])
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
        queue.push_batch([(0, "a", None)])
        replacement = Parameter("x", int, default=2, _config=KnotConfig(id="a"))
        shed.knots["a"] = replacement
        gate = _RefuseIds(set())

        # Act
        queue.pop_admissible(gate, shed)

        # Assert
        self.assertIs(gate.offered_knots[0], replacement)


class TestReadyQueueGroups(unittest.TestCase):
    """One FIFO per concurrency group (PIR-841 slice 2, design §6)."""

    def test_a_refused_group_head_does_not_block_another_group(self) -> None:
        # Arrange: the api head became ready first and is refused.
        queue = ReadyQueue()
        shed = _shed("api0", "api1", "local0")
        queue.push_batch([(0, "api0", "api"), (1, "api1", "api")])
        queue.push_batch([(2, "local0", None)])
        gate = _RefuseIds({"api0"})

        # Act
        admitted = queue.pop_admissible(gate, shed)

        # Assert: local0 is admitted past the refused api head ...
        self.assertEqual(admitted, ("local0", AdmissionTicket(knot_id="local0")))
        # ... and nothing queued behind that head in its own group was offered.
        self.assertEqual(gate.offered, ["api0", "local0"])
        self.assertEqual(len(queue), 2)

    def test_a_refused_head_keeps_its_group_in_fifo_order(self) -> None:
        # Arrange
        queue = ReadyQueue()
        shed = _shed("a0", "a1", "a2")
        queue.push_batch([(0, "a0", "api"), (1, "a1", "api"), (2, "a2", "api")])
        gate = _RefuseIds({"a0"})

        # Act
        refused = queue.pop_admissible(gate, shed)
        gate.refused.clear()
        popped = _drain(queue, gate, shed)

        # Assert: a1 never overtook the refused a0.
        self.assertIsNone(refused)
        self.assertEqual(popped, ["a0", "a1", "a2"])

    def test_admits_across_groups_in_readiness_order(self) -> None:
        # Arrange: interleaved readiness across three groups.
        queue = ReadyQueue()
        shed = _shed("g1", "l1", "h1", "g2", "l2")
        queue.push_batch([(4, "g1", "api")])
        queue.push_batch([(3, "l1", None), (0, "h1", "db")])
        queue.push_batch([(1, "g2", "api"), (2, "l2", None)])

        # Act
        popped = _drain(queue, UnboundedAdmissionGate(), shed)

        # Assert: batch first, then topological index within a batch.
        self.assertEqual(popped, ["g1", "h1", "l1", "g2", "l2"])

    def test_a_later_ready_knot_in_a_group_waits_behind_an_earlier_one(self) -> None:
        # Arrange: "a_late" sorts first topologically but became ready later.
        queue = ReadyQueue()
        shed = _shed("z_early", "a_late")
        queue.push_batch([(9, "z_early", "api")])
        queue.push_batch([(0, "a_late", "api")])

        # Act
        popped = _drain(queue, UnboundedAdmissionGate(), shed)

        # Assert
        self.assertEqual(popped, ["z_early", "a_late"])

    def test_returns_none_when_every_group_head_is_refused(self) -> None:
        # Arrange
        queue = ReadyQueue()
        shed = _shed("a", "b", "c")
        queue.push_batch([(0, "a", "api"), (1, "b", "db"), (2, "c", None)])
        gate = _RefuseIds({"a", "b", "c"})

        # Act
        admitted = queue.pop_admissible(gate, shed)

        # Assert
        self.assertIsNone(admitted)
        self.assertEqual(sorted(gate.offered), ["a", "b", "c"])
        self.assertEqual(len(queue), 3)

    def test_an_emptied_group_is_forgotten(self) -> None:
        # Arrange
        queue = ReadyQueue()
        shed = _shed("a", "b")
        queue.push_batch([(0, "a", "api")])
        _drain(queue, UnboundedAdmissionGate(), shed)
        queue.push_batch([(1, "b", None)])
        gate = _RefuseIds(set())

        # Act
        popped = _drain(queue, gate, shed)

        # Assert: the empty api FIFO is not offered again.
        self.assertEqual(popped, ["b"])
        self.assertEqual(gate.offered, ["b"])
        self.assertFalse(queue)
