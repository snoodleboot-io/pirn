"""Unit tests for UnboundedAdmission."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.engine.admission.admission import Admission
from pirn.engine.admission.admission_ticket import AdmissionTicket
from pirn.engine.admission.unbounded_admission import UnboundedAdmission


def _param(knot_id: str) -> Parameter:
    return Parameter("x", int, default=1, _config=KnotConfig(id=knot_id))


class TestUnboundedAdmission(unittest.IsolatedAsyncioTestCase):
    def test_is_an_admission(self) -> None:
        # Arrange / Act
        gate = UnboundedAdmission()

        # Assert
        self.assertIsInstance(gate, Admission)

    def test_admits_a_knot_with_a_ticket_naming_it(self) -> None:
        # Arrange
        gate = UnboundedAdmission()

        # Act
        ticket = gate.try_admit(_param("px"))

        # Assert
        self.assertEqual(ticket, AdmissionTicket(knot_id="px"))

    def test_never_refuses_however_many_are_held(self) -> None:
        # Arrange
        gate = UnboundedAdmission()

        # Act
        tickets = [gate.try_admit(_param(f"p{i}")) for i in range(1000)]

        # Assert
        self.assertTrue(all(t is not None for t in tickets))

    def test_always_has_capacity(self) -> None:
        self.assertTrue(UnboundedAdmission().has_capacity())

    def test_release_accepts_its_ticket(self) -> None:
        # Arrange
        gate = UnboundedAdmission()
        ticket = gate.try_admit(_param("px"))

        # Act
        gate.release(ticket)

        # Assert: releasing frees nothing, so the gate still admits.
        self.assertIsNotNone(gate.try_admit(_param("px")))

    async def test_wait_for_release_returns_at_once(self) -> None:
        # Arrange
        gate = UnboundedAdmission()

        # Act
        outcome = await gate.wait_for_release()

        # Assert
        self.assertIsNone(outcome)
