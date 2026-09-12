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

    def test_is_frozen(self) -> None:
        # Arrange
        ticket = AdmissionTicket(knot_id="k1")

        # Act / Assert
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ticket.knot_id = "other"  # type: ignore[misc]

    def test_tickets_for_the_same_knot_are_equal(self) -> None:
        # Arrange / Act
        first = AdmissionTicket(knot_id="k1")
        second = AdmissionTicket(knot_id="k1")

        # Assert
        self.assertEqual(first, second)
        self.assertNotEqual(first, AdmissionTicket(knot_id="k2"))
