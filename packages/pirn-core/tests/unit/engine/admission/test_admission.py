"""Unit tests for the Admission interface."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.engine.admission.admission import Admission
from pirn.engine.admission.admission_ticket import AdmissionTicket


class TestAdmissionInterface(unittest.IsolatedAsyncioTestCase):
    def test_try_admit_must_be_implemented(self) -> None:
        # Arrange
        gate = Admission()
        knot = Parameter("x", int, default=1, _config=KnotConfig(id="px"))

        # Act / Assert
        with self.assertRaisesRegex(NotImplementedError, "try_admit"):
            gate.try_admit(knot)

    def test_has_capacity_must_be_implemented(self) -> None:
        # Arrange
        gate = Admission()

        # Act / Assert
        with self.assertRaisesRegex(NotImplementedError, "has_capacity"):
            gate.has_capacity()

    def test_release_must_be_implemented(self) -> None:
        # Arrange
        gate = Admission()

        # Act / Assert
        with self.assertRaisesRegex(NotImplementedError, "release"):
            gate.release(AdmissionTicket(knot_id="px"))

    async def test_wait_for_release_must_be_implemented(self) -> None:
        # Arrange
        gate = Admission()

        # Act / Assert
        with self.assertRaisesRegex(NotImplementedError, "wait_for_release"):
            await gate.wait_for_release()
