"""Slot-free admission of container knots (ADR agents-speaks-core, WS0b).

A container knot (``Knot._holds_admission_slot`` is ``False``) is admitted
without consulting the gate, even when the gate is full, and its ticket says
so (``held`` is ``False``) so the engine never hands it back to the gate.
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.engine.admission.admission_ticket import AdmissionTicket
from pirn.engine.admission.limited_admission import LimitedAdmission
from pirn.engine.scheduling.ready_queue import ReadyQueue
from pirn.engine.shed.shed import Shed


class _Leaf(Knot):
    async def process(self, **_: Any) -> None:
        return None


class _Container(Knot):
    _holds_admission_slot: ClassVar[bool] = False

    async def process(self, **_: Any) -> None:
        return None


def _shed(*knots: Knot) -> Shed:
    return Shed.from_terminals(list(knots))


class TestAdmissionTicketHeld(unittest.TestCase):
    def test_a_gate_issued_ticket_is_held(self) -> None:
        gate = LimitedAdmission(ConcurrencyLimits(max_in_flight=1))
        ticket = gate.try_admit(_Leaf(_config=KnotConfig(id="a")))
        assert ticket is not None
        self.assertTrue(ticket.held)

    def test_held_defaults_to_true(self) -> None:
        self.assertTrue(AdmissionTicket(knot_id="a").held)


class TestContainersAreAdmittedWithoutTheGate(unittest.TestCase):
    def test_a_container_is_admitted_when_the_gate_is_full(self) -> None:
        # Arrange: the single slot is taken by a leaf.
        gate = LimitedAdmission(ConcurrencyLimits(max_in_flight=1))
        busy = gate.try_admit(_Leaf(_config=KnotConfig(id="busy")))
        assert busy is not None
        container = _Container(_config=KnotConfig(id="sub"))
        queue = ReadyQueue()
        queue.push_batch([(0, "sub", None)])

        # Act
        admitted = queue.pop_admissible(gate, _shed(container))

        # Assert: admitted, slot-free, and the gate saw nothing.
        assert admitted is not None
        knot_id, ticket = admitted
        self.assertEqual(knot_id, "sub")
        self.assertFalse(ticket.held)
        self.assertEqual(gate.in_flight, 1)

    def test_a_leaf_ahead_of_a_container_is_still_refused_by_a_full_gate(self) -> None:
        # Arrange: readiness order is leaf then container; the gate is full.
        gate = LimitedAdmission(ConcurrencyLimits(max_in_flight=1))
        busy = gate.try_admit(_Leaf(_config=KnotConfig(id="busy")))
        assert busy is not None
        leaf = _Leaf(_config=KnotConfig(id="leaf"))
        container = _Container(_config=KnotConfig(id="sub"))
        queue = ReadyQueue()
        queue.push_batch([(0, "leaf", None), (1, "sub", None)])

        # Act / Assert: nothing is offered past the refused head, in order.
        self.assertIsNone(queue.pop_admissible(gate, _shed(leaf, container)))
        self.assertEqual(len(queue), 2)

    def test_a_container_head_is_offered_before_a_later_leaf_when_full(self) -> None:
        gate = LimitedAdmission(ConcurrencyLimits(max_in_flight=1))
        busy = gate.try_admit(_Leaf(_config=KnotConfig(id="busy")))
        assert busy is not None
        leaf = _Leaf(_config=KnotConfig(id="leaf"))
        container = _Container(_config=KnotConfig(id="sub"))
        queue = ReadyQueue()
        queue.push_batch([(0, "sub", None), (1, "leaf", None)])

        admitted = queue.pop_admissible(gate, _shed(leaf, container))

        assert admitted is not None
        self.assertEqual(admitted[0], "sub")
        self.assertIsNone(queue.pop_admissible(gate, _shed(leaf, container)))

    def test_a_leaf_still_takes_a_real_slot(self) -> None:
        gate = LimitedAdmission(ConcurrencyLimits(max_in_flight=2))
        leaf = _Leaf(_config=KnotConfig(id="leaf"))
        queue = ReadyQueue()
        queue.push_batch([(0, "leaf", None)])

        admitted = queue.pop_admissible(gate, _shed(leaf))

        assert admitted is not None
        self.assertTrue(admitted[1].held)
        self.assertEqual(gate.in_flight, 1)
