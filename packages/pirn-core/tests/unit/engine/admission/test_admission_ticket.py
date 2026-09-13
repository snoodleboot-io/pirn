"""Unit tests for AdmissionTicket."""

from __future__ import annotations

import dataclasses
import unittest

from pirn.engine.admission.admission_ticket import AdmissionTicket


class TestAdmissionTicket(unittest.TestCase):
    def test_carries_the_knot_id(self) -> None:
        # Arrange / Act
        ticket = AdmissionTicket(knot_id="k1")

        # Assert
        self.assertEqual(ticket.knot_id, "k1")

    def test_holds_no_group_slot_by_default(self) -> None:
        self.assertIsNone(AdmissionTicket(knot_id="k1").group)

    def test_records_the_group_slot_it_holds(self) -> None:
        self.assertEqual(AdmissionTicket(knot_id="k1", group="api").group, "api")

    def test_is_frozen(self) -> None:
        # Arrange
        ticket = AdmissionTicket(knot_id="k1")

        # Act / Assert
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ticket.knot_id = "other"  # type: ignore[misc]
