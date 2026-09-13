"""A ``LimitedAdmissionGate`` shared across a run tree (ADR agents-speaks-core, WS0b).

One gate is inherited by identity into every inner run, so it meets two
things a per-run gate never did: tickets from different runs whose knots
share an id, and callers on other threads' event loops (an inner run under
``ThreadDispatcher``).  These tests pin the two behaviours that make sharing
safe: slots are tracked per ticket, and a release from another thread wakes
a waiter parked on this loop.
"""

from __future__ import annotations

import asyncio
import threading
import unittest
from typing import Any

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.engine.admission.admission_release_error import AdmissionReleaseError
from pirn.engine.admission.limited_admission_gate import LimitedAdmissionGate


class _Noop(Knot):
    async def process(self, **_: Any) -> None:
        return None


def _knot(knot_id: str, group: str | None = None) -> Knot:
    return _Noop(_config=KnotConfig(id=knot_id, concurrency_group=group))


class TestTicketsAreTrackedByIdentity(unittest.TestCase):
    def test_two_runs_admitting_the_same_knot_id_hold_two_slots(self) -> None:
        # Arrange: an outer and an inner run each have a knot called "d".
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=3))

        # Act
        outer = gate.try_admit(_knot("d"))
        inner = gate.try_admit(_knot("d"))

        # Assert
        assert outer is not None and inner is not None
        self.assertEqual(gate.in_flight, 2)

    def test_each_ticket_releases_its_own_slot(self) -> None:
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=2))
        outer = gate.try_admit(_knot("d"))
        inner = gate.try_admit(_knot("d"))
        assert outer is not None and inner is not None

        gate.release(inner)
        self.assertEqual(gate.in_flight, 1)
        gate.release(outer)
        self.assertEqual(gate.in_flight, 0)

    def test_a_same_looking_ticket_from_elsewhere_is_refused(self) -> None:
        # Arrange: a ticket equal by value to a held one, but not the one issued.
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=2))
        issued = gate.try_admit(_knot("d"))
        assert issued is not None
        lookalike = type(issued)(knot_id="d", group=None)
        self.assertEqual(lookalike, issued)

        # Act / Assert
        with self.assertRaises(AdmissionReleaseError):
            gate.release(lookalike)
        self.assertEqual(gate.in_flight, 1)

    def test_a_double_release_still_raises(self) -> None:
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=2))
        ticket = gate.try_admit(_knot("d"))
        assert ticket is not None
        gate.release(ticket)
        with self.assertRaises(AdmissionReleaseError):
            gate.release(ticket)


class TestReleaseFromAnotherThreadWakesThisLoop(unittest.IsolatedAsyncioTestCase):
    async def test_a_waiter_is_woken_by_a_release_on_a_worker_thread(self) -> None:
        # Arrange: the gate is full; a waiter parks on this loop.
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=1))
        ticket = gate.try_admit(_knot("slow"))
        assert ticket is not None
        waiter = asyncio.ensure_future(gate.wait_for_release())
        await asyncio.sleep(0)
        self.assertFalse(waiter.done())

        # Act: the release happens on another thread, as it does when an inner
        # run on a ThreadDispatcher worker finishes a leaf.
        releaser = threading.Thread(target=gate.release, args=(ticket,))
        releaser.start()
        releaser.join(timeout=5)

        # Assert: woken here, on this loop, without a hang.
        await asyncio.wait_for(waiter, timeout=5)
        self.assertEqual(gate.in_flight, 0)

    async def test_a_waiter_on_another_loop_is_woken_too(self) -> None:
        # Arrange: a worker thread runs its own loop and parks on the gate --
        # the inner-run-under-ThreadDispatcher shape -- while this loop holds
        # the only slot.
        gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=1))
        ticket = gate.try_admit(_knot("outer"))
        assert ticket is not None
        parked = threading.Event()
        woken: list[bool] = []

        async def _park() -> None:
            parked.set()
            await asyncio.wait_for(gate.wait_for_release(), timeout=5)
            woken.append(True)

        # design-decision-override: the worker must own a loop of its own,
        # which asyncio.run on a plain thread is the direct way to arrange.
        worker = threading.Thread(target=asyncio.run, args=(_park(),))
        worker.start()
        self.assertTrue(parked.wait(timeout=5))
        await asyncio.sleep(0.05)

        # Act
        gate.release(ticket)
        worker.join(timeout=5)

        # Assert
        self.assertEqual(woken, [True])
