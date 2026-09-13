"""Unit tests for LimitedAdmissionGate (PIR-841 slice 2)."""

from __future__ import annotations

import asyncio
import unittest

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.concurrency.undefined_concurrency_group_error import (
    UndefinedConcurrencyGroupError,
)
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.engine.admission.admission_gate import AdmissionGate
from pirn.engine.admission.admission_release_error import AdmissionReleaseError
from pirn.engine.admission.admission_ticket import AdmissionTicket
from pirn.engine.admission.limited_admission_gate import LimitedAdmissionGate
from pirn.exceptions.pirn_error import PirnError


def _knot(knot_id: str, group: str | None = None) -> Parameter:
    return Parameter("x", int, default=1, _config=KnotConfig(id=knot_id, concurrency_group=group))


def _admit_all(gate: LimitedAdmissionGate, *knots: Parameter) -> list[AdmissionTicket | None]:
    return [gate.try_admit(k) for k in knots]


class TestLimitedAdmissionGateGlobalCap(unittest.TestCase):
    def test_is_an_admission_gate(self) -> None:
        self.assertIsInstance(
            LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=1)), AdmissionGate
        )

    def test_admits_up_to_the_global_cap(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=2))

        # Act
        tickets = _admit_all(gate, _knot("a"), _knot("b"), _knot("c"))

        # Assert
        self.assertEqual(tickets[0], AdmissionTicket(knot_id="a"))
        self.assertEqual(tickets[1], AdmissionTicket(knot_id="b"))
        self.assertIsNone(tickets[2])
        self.assertEqual(gate.in_flight, 2)

    def test_release_frees_a_global_slot(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=1))
        first = gate.try_admit(_knot("a"))
        assert first is not None
        refused = gate.try_admit(_knot("b"))

        # Act
        gate.release(first)
        admitted = gate.try_admit(_knot("b"))

        # Assert
        self.assertIsNone(refused)
        self.assertEqual(admitted, AdmissionTicket(knot_id="b"))

    def test_grouped_knots_count_against_the_global_cap(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=2, groups={"api": 5}))

        # Act
        tickets = _admit_all(gate, _knot("a", "api"), _knot("b"), _knot("c", "api"))

        # Assert
        self.assertIsNone(tickets[2])


class TestLimitedAdmissionGateGroupCap(unittest.TestCase):
    def test_admits_up_to_the_group_cap(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(groups={"api": 2}))

        # Act
        tickets = _admit_all(gate, _knot("a", "api"), _knot("b", "api"), _knot("c", "api"))

        # Assert
        self.assertEqual(tickets[0], AdmissionTicket(knot_id="a", group="api"))
        self.assertEqual(tickets[1], AdmissionTicket(knot_id="b", group="api"))
        self.assertIsNone(tickets[2])
        self.assertEqual(gate.in_flight_in("api"), 2)

    def test_a_full_group_does_not_refuse_ungrouped_knots(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(groups={"api": 1}))
        gate.try_admit(_knot("a", "api"))

        # Act
        tickets = _admit_all(gate, *(_knot(f"local{i}") for i in range(100)))

        # Assert: no global cap, so every ungrouped knot is admitted.
        self.assertTrue(all(t is not None for t in tickets))

    def test_a_full_group_does_not_refuse_another_group(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(groups={"api": 1, "db": 1}))
        gate.try_admit(_knot("a", "api"))

        # Act
        ticket = gate.try_admit(_knot("d", "db"))

        # Assert
        self.assertEqual(ticket, AdmissionTicket(knot_id="d", group="db"))

    def test_release_frees_a_group_slot(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(groups={"api": 1}))
        first = gate.try_admit(_knot("a", "api"))
        assert first is not None

        # Act
        gate.release(first)
        second = gate.try_admit(_knot("b", "api"))

        # Assert
        self.assertEqual(second, AdmissionTicket(knot_id="b", group="api"))
        self.assertEqual(gate.in_flight_in("api"), 1)

    def test_a_group_the_limits_do_not_define_raises(self) -> None:
        # Arrange: a typo ("open_ai" for "openai") must not silently lift a cap.
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=3, groups={"openai": 1}))

        # Act / Assert
        with self.assertRaises(UndefinedConcurrencyGroupError) as caught:
            gate.try_admit(_knot("llm0", "open_ai"))
        message = str(caught.exception)
        self.assertIn("llm0", message)
        self.assertIn("open_ai", message)
        self.assertIn("openai", message)
        self.assertEqual(caught.exception.knot_id, "llm0")
        self.assertEqual(caught.exception.group, "open_ai")
        self.assertEqual(caught.exception.defined_groups, ("openai",))
        self.assertEqual(gate.in_flight, 0)

    def test_group_tags_are_ignored_when_the_limits_define_no_groups(self) -> None:
        # Arrange: the same tagged graph may run under a global cap alone.
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=3))

        # Act
        tickets = _admit_all(gate, *(_knot(f"u{i}", "anything") for i in range(4)))

        # Assert
        self.assertEqual([t is not None for t in tickets], [True, True, True, False])
        self.assertEqual(tickets[0], AdmissionTicket(knot_id="u0"))

    def test_undefined_group_error_is_a_pirn_error(self) -> None:
        self.assertTrue(issubclass(UndefinedConcurrencyGroupError, PirnError))


class TestLimitedAdmissionGateCapacity(unittest.TestCase):
    def test_has_capacity_until_the_global_cap_is_full(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=1))

        # Act
        before = gate.has_capacity()
        ticket = gate.try_admit(_knot("a"))

        # Assert
        assert ticket is not None
        self.assertTrue(before)
        self.assertFalse(gate.has_capacity())
        gate.release(ticket)
        self.assertTrue(gate.has_capacity())

    def test_a_group_only_gate_always_has_global_capacity(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(groups={"api": 1}))
        gate.try_admit(_knot("a", "api"))

        # Act / Assert
        self.assertTrue(gate.has_capacity())


class TestLimitedAdmissionGateBothCaps(unittest.TestCase):
    def test_the_tighter_global_cap_wins(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=2, groups={"api": 5}))

        # Act
        tickets = _admit_all(gate, *(_knot(f"a{i}", "api") for i in range(5)))

        # Assert
        self.assertEqual(sum(t is not None for t in tickets), 2)

    def test_the_tighter_group_cap_wins(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=5, groups={"api": 2}))

        # Act
        tickets = _admit_all(gate, *(_knot(f"a{i}", "api") for i in range(5)))

        # Assert
        self.assertEqual(sum(t is not None for t in tickets), 2)

    def test_a_refusal_takes_no_slot_at_either_level(self) -> None:
        # Arrange: the group is full; asking again must not leak a global slot.
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=3, groups={"api": 1}))
        gate.try_admit(_knot("a0", "api"))

        # Act
        for i in range(10):
            gate.try_admit(_knot(f"a{i + 1}", "api"))

        # Assert
        self.assertEqual(gate.in_flight, 1)
        self.assertIsNotNone(gate.try_admit(_knot("b")))
        self.assertIsNotNone(gate.try_admit(_knot("c")))


class TestLimitedAdmissionGateRelease(unittest.TestCase):
    def test_releasing_a_ticket_twice_raises(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=2))
        ticket = gate.try_admit(_knot("a"))
        assert ticket is not None
        gate.release(ticket)

        # Act / Assert
        with self.assertRaises(AdmissionReleaseError):
            gate.release(ticket)
        self.assertEqual(gate.in_flight, 0)

    def test_releasing_a_ticket_it_did_not_issue_raises(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=2))

        # Act / Assert
        with self.assertRaises(AdmissionReleaseError):
            gate.release(AdmissionTicket(knot_id="stranger"))

    def test_release_error_is_a_pirn_error(self) -> None:
        self.assertTrue(issubclass(AdmissionReleaseError, PirnError))


class TestLimitedAdmissionGateWaiting(unittest.IsolatedAsyncioTestCase):
    async def test_wait_for_release_returns_at_once_when_nothing_is_held(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=1))

        # Act
        outcome = await asyncio.wait_for(gate.wait_for_release(), timeout=1.0)

        # Assert
        self.assertIsNone(outcome)

    async def test_wait_for_release_wakes_when_a_slot_is_released(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=1))
        ticket = gate.try_admit(_knot("a"))
        assert ticket is not None
        waiter = asyncio.create_task(gate.wait_for_release())
        await asyncio.sleep(0)
        self.assertFalse(waiter.done())

        # Act
        gate.release(ticket)

        # Assert
        await asyncio.wait_for(waiter, timeout=1.0)
        self.assertIsNotNone(gate.try_admit(_knot("b")))

    async def test_a_cancelled_waiter_does_not_break_a_later_release(self) -> None:
        # Arrange
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=1))
        ticket = gate.try_admit(_knot("a"))
        assert ticket is not None
        waiter = asyncio.create_task(gate.wait_for_release())
        await asyncio.sleep(0)
        waiter.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiter

        # Act
        gate.release(ticket)

        # Assert
        self.assertEqual(gate.in_flight, 0)


if __name__ == "__main__":
    unittest.main()
