"""Mirrored tests for backpressure/bound enforcement (PIR-301).

Verifies the semaphore bound is respected under load, that the default
(unbounded queue) *queues* excess callers rather than failing, that a set
``max_queue_depth`` sheds load with a typed :class:`asyncio.QueueFull`, and that
``acquire_timeout`` is honoured.
"""

from __future__ import annotations

import asyncio
import warnings
from typing import Any

import pytest
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.engine.admission.admission_gate import AdmissionGate

from pirn_agents.performance.backpressure_semaphore import BackpressureSemaphore
from pirn_agents.performance.concurrency_config import ConcurrencyConfig


class _BackpressureProbe(Knot):
    """A knot built only for ``try_admit``'s identity; never dispatched."""

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction:
    def test_rejects_non_config(self) -> None:
        with pytest.raises(TypeError, match="ConcurrencyConfig"):
            BackpressureSemaphore(object())  # type: ignore[arg-type]

    def test_warns_deprecated(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            BackpressureSemaphore(ConcurrencyConfig())
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_is_an_admission_gate(self) -> None:
        assert isinstance(BackpressureSemaphore(ConcurrencyConfig()), AdmissionGate)


class TestBoundEnforcement:
    async def test_never_exceeds_max_concurrency(self) -> None:
        sem = BackpressureSemaphore(ConcurrencyConfig(max_concurrency=3))
        peak = 0
        live = 0
        lock = asyncio.Lock()

        async def worker() -> None:
            nonlocal peak, live
            async with sem.slot():
                async with lock:
                    live += 1
                    peak = max(peak, live)
                await asyncio.sleep(0.02)
                async with lock:
                    live -= 1

        await asyncio.gather(*(worker() for _ in range(12)))
        assert peak <= 3
        assert sem.in_flight == 0

    async def test_excess_callers_queue_by_default(self) -> None:
        # max_concurrency=1, unbounded queue: the second acquirer waits.
        sem = BackpressureSemaphore(ConcurrencyConfig(max_concurrency=1))
        await sem.acquire()
        waiter = asyncio.ensure_future(sem.acquire())
        await asyncio.sleep(0)
        assert waiter.done() is False  # queued, not failed
        assert sem.waiting == 1
        sem.release()
        await waiter  # unblocks once the slot frees
        assert sem.in_flight == 1
        sem.release()


class TestBackpressureShedding:
    async def test_queue_full_raises_when_depth_exceeded(self) -> None:
        # One slot, room for a single waiter; a second waiter is shed.
        sem = BackpressureSemaphore(ConcurrencyConfig(max_concurrency=1, max_queue_depth=1))
        await sem.acquire()  # holder
        waiter = asyncio.ensure_future(sem.acquire())  # fills the queue
        await asyncio.sleep(0)
        assert sem.waiting == 1
        with pytest.raises(asyncio.QueueFull):
            await sem.acquire()
        # Clean up the parked waiter.
        sem.release()
        await waiter
        sem.release()


class TestAcquireTimeout:
    async def test_timeout_raises_when_no_slot_frees(self) -> None:
        sem = BackpressureSemaphore(ConcurrencyConfig(max_concurrency=1, acquire_timeout=0.02))
        await sem.acquire()
        with pytest.raises(TimeoutError):
            await sem.acquire()
        assert sem.waiting == 0  # waiter cleaned up after timeout
        sem.release()


class TestAdmissionGateSurface:
    """``BackpressureSemaphore`` is a real ``AdmissionGate`` -- not only a facade."""

    def test_try_admit_and_release_by_ticket(self) -> None:
        sem = BackpressureSemaphore(ConcurrencyConfig(max_concurrency=1))
        probe = _BackpressureProbe(_config=KnotConfig(id="probe"))

        ticket = sem.try_admit(probe)
        assert ticket is not None
        assert sem.try_admit(probe) is None  # capacity exhausted
        sem.release(ticket)
        assert sem.has_capacity()

    def test_set_limit_and_current_limit(self) -> None:
        sem = BackpressureSemaphore(ConcurrencyConfig(max_concurrency=2))
        assert sem.current_limit(None) == 2
        sem.set_limit(None, 5)
        assert sem.current_limit(None) == 5
