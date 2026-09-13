"""``AdmissionGate.set_limit`` / ``current_limit`` (ADR agents-speaks-core, WS0).

A live cap change applies to every admission from then on and never touches
a ticket already issued.
"""

from __future__ import annotations

import unittest

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.engine.admission.admission_gate import AdmissionGate
from pirn.engine.admission.admission_limit_error import AdmissionLimitError
from pirn.engine.admission.limited_admission_gate import LimitedAdmissionGate
from pirn.engine.admission.unbounded_admission_gate import UnboundedAdmissionGate
from pirn.exceptions.pirn_error import PirnError


def _knot(knot_id: str, group: str | None = None) -> Parameter:
    return Parameter("x", int, default=1, _config=KnotConfig(id=knot_id, concurrency_group=group))


class TestInterface(unittest.TestCase):
    def test_base_methods_must_be_implemented(self) -> None:
        gate = AdmissionGate()
        with self.assertRaisesRegex(NotImplementedError, "current_limit"):
            gate.current_limit("api")
        with self.assertRaisesRegex(NotImplementedError, "set_limit"):
            gate.set_limit("api", 2)

    def test_limit_error_is_a_pirn_error(self) -> None:
        self.assertTrue(issubclass(AdmissionLimitError, PirnError))


class TestLimitedGateGroupLimits(unittest.TestCase):
    def test_current_limit_reflects_the_declared_limits(self) -> None:
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=3, groups={"api": 1}))
        self.assertEqual(gate.current_limit(None), 3)
        self.assertEqual(gate.current_limit("api"), 1)
        self.assertIsNone(gate.current_limit("other"))

    def test_raising_a_group_limit_admits_more(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(groups={"api": 1}))
        first = gate.try_admit(_knot("a", "api"))
        refused = gate.try_admit(_knot("b", "api"))

        # Act
        gate.set_limit("api", 2)
        admitted = gate.try_admit(_knot("b", "api"))

        # Assert
        self.assertIsNotNone(first)
        self.assertIsNone(refused)
        self.assertIsNotNone(admitted)
        self.assertEqual(gate.current_limit("api"), 2)
        self.assertEqual(gate.in_flight_in("api"), 2)

    def test_lowering_a_group_limit_keeps_issued_tickets_and_refuses_new_ones(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(groups={"api": 2}))
        a = gate.try_admit(_knot("a", "api"))
        b = gate.try_admit(_knot("b", "api"))
        assert a is not None and b is not None

        # Act
        gate.set_limit("api", 1)

        # Assert: both tickets still stand; nothing new gets in until two
        # releases bring the group under the new cap.
        self.assertEqual(gate.in_flight_in("api"), 2)
        self.assertIsNone(gate.try_admit(_knot("c", "api")))
        gate.release(a)
        self.assertIsNone(gate.try_admit(_knot("c", "api")))
        gate.release(b)
        self.assertIsNotNone(gate.try_admit(_knot("c", "api")))

    def test_the_declared_limits_are_unchanged(self) -> None:
        limits = ConcurrencyLimits(groups={"api": 1})
        gate = LimitedAdmissionGate(limits)
        gate.set_limit("api", 5)
        self.assertIs(gate.limits, limits)
        self.assertEqual(limits.groups["api"], 1)

    def test_an_undefined_group_is_refused(self) -> None:
        gate = LimitedAdmissionGate(ConcurrencyLimits(groups={"api": 1}))
        with self.assertRaisesRegex(AdmissionLimitError, "'other'"):
            gate.set_limit("other", 2)

    def test_a_limit_below_one_is_refused(self) -> None:
        gate = LimitedAdmissionGate(ConcurrencyLimits(groups={"api": 1}))
        for bad in (0, -1, True):
            with self.subTest(limit=bad), self.assertRaises(AdmissionLimitError):
                gate.set_limit("api", bad)  # type: ignore[arg-type]
        self.assertEqual(gate.current_limit("api"), 1)


class TestLimitedGateRunWideLimit(unittest.TestCase):
    def test_raising_the_run_wide_cap_admits_more(self) -> None:
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=1))
        gate.try_admit(_knot("a"))
        self.assertFalse(gate.has_capacity())
        gate.set_limit(None, 2)
        self.assertTrue(gate.has_capacity())
        self.assertIsNotNone(gate.try_admit(_knot("b")))

    def test_lowering_the_run_wide_cap_refuses_until_released(self) -> None:
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=2))
        a = gate.try_admit(_knot("a"))
        gate.try_admit(_knot("b"))
        assert a is not None
        gate.set_limit(None, 1)
        self.assertFalse(gate.has_capacity())
        self.assertIsNone(gate.try_admit(_knot("c")))
        gate.release(a)
        self.assertFalse(gate.has_capacity())

    def test_group_only_limits_can_gain_a_run_wide_cap(self) -> None:
        gate = LimitedAdmissionGate(ConcurrencyLimits(groups={"api": 4}))
        self.assertIsNone(gate.current_limit(None))
        gate.set_limit(None, 1)
        self.assertEqual(gate.current_limit(None), 1)
        gate.try_admit(_knot("a"))
        self.assertIsNone(gate.try_admit(_knot("b")))


class TestUnboundedGate(unittest.TestCase):
    def test_reports_no_limits(self) -> None:
        gate = UnboundedAdmissionGate()
        self.assertIsNone(gate.current_limit(None))
        self.assertIsNone(gate.current_limit("api"))

    def test_refuses_to_set_a_limit(self) -> None:
        with self.assertRaisesRegex(AdmissionLimitError, "ConcurrencyLimits"):
            UnboundedAdmissionGate().set_limit("api", 2)
