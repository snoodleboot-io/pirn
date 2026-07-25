"""Mirrored tests for backpressure/bound enforcement (PIR-301).

Verifies the semaphore bound is respected under load, that the default
(unbounded queue) *queues* excess callers rather than failing, that a set
``max_queue_depth`` sheds load with a typed :class:`asyncio.QueueFull`, and that
``acquire_timeout`` is honoured.
"""

from __future__ import annotations

import asyncio

import pytest

from pirn_agents.performance.backpressure_semaphore import BackpressureSemaphore
from pirn_agents.performance.concurrency_config import ConcurrencyConfig


class TestConstruction:
    def test_rejects_non_config(self) -> None:
        with pytest.raises(TypeError, match="ConcurrencyConfig"):
            BackpressureSemaphore(object())  # type: ignore[arg-type]


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
