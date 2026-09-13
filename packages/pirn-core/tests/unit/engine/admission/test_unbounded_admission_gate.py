"""Unit tests for UnboundedAdmissionGate."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.engine.admission.admission_gate import AdmissionGate
from pirn.engine.admission.admission_ticket import AdmissionTicket
from pirn.engine.admission.unbounded_admission_gate import UnboundedAdmissionGate


def _param(knot_id: str) -> Parameter:
    return Parameter("x", int, default=1, _config=KnotConfig(id=knot_id))


class TestUnboundedAdmissionGate(unittest.IsolatedAsyncioTestCase):
    def test_is_an_admission_gate(self) -> None:
        # Arrange / Act
        gate = UnboundedAdmissionGate()

        # Assert
        self.assertIsInstance(gate, AdmissionGate)

    def test_admits_a_knot_with_a_ticket_naming_it(self) -> None:
        # Arrange
        gate = UnboundedAdmissionGate()

        # Act
        ticket = gate.try_admit(_param("px"))

        # Assert
        self.assertEqual(ticket, AdmissionTicket(knot_id="px"))

    def test_never_refuses_however_many_are_held(self) -> None:
        # Arrange
        gate = UnboundedAdmissionGate()

        # Act
        tickets = [gate.try_admit(_param(f"p{i}")) for i in range(1000)]

        # Assert
        self.assertTrue(all(t is not None for t in tickets))

    def test_release_accepts_its_ticket(self) -> None:
        # Arrange
        gate = UnboundedAdmissionGate()
        ticket = gate.try_admit(_param("px"))

        # Act
        gate.release(ticket)

        # Assert: releasing frees nothing, so the gate still admits.
        self.assertIsNotNone(gate.try_admit(_param("px")))

    async def test_wait_for_release_returns_at_once(self) -> None:
        # Arrange
        gate = UnboundedAdmissionGate()

        # Act
        outcome = await gate.wait_for_release()

        # Assert
        self.assertIsNone(outcome)
