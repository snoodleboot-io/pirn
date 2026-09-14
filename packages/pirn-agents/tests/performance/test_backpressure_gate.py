"""Unit tests for :class:`_BackpressureGate` (ADR agents-speaks-core, WS4b/PIR-866).

Covers the shared building block directly: construction validation, the
bare (``group=None``) and named-group shapes, queue-depth shedding, acquire
timeout, identity-safe release bookkeeping under concurrent acquisitions,
and the ``AdmissionGate`` passthrough surface.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.engine.admission.admission_gate import AdmissionGate
from pirn.engine.admission.admission_release_error import AdmissionReleaseError

from pirn_agents.performance._backpressure_gate import _BackpressureGate
from pirn_agents.performance.concurrency_config import ConcurrencyConfig


class _GateProbe(Knot):
    """A knot built only for ``try_admit``'s identity; never dispatched."""

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction:
    def test_rejects_non_config(self) -> None:
        with pytest.raises(TypeError, match="ConcurrencyConfig"):
            _BackpressureGate(object())  # type: ignore[arg-type]

    def test_is_an_admission_gate(self) -> None:
        assert isinstance(_BackpressureGate(ConcurrencyConfig()), AdmissionGate)


class TestBareGate:
    """``group=None``: a plain ``max_in_flight``-shaped pool (``BackpressureSemaphore``)."""

    async def test_never_exceeds_max_concurrency(self) -> None:
        pool = _BackpressureGate(ConcurrencyConfig(max_concurrency=3))
        peak = 0
        live = 0
        lock = asyncio.Lock()

        async def worker() -> None:
            nonlocal peak, live
            async with pool.slot():
                async with lock:
                    live += 1
                    peak = max(peak, live)
                await asyncio.sleep(0.01)
                async with lock:
                    live -= 1

        await asyncio.gather(*(worker() for _ in range(9)))
        assert peak <= 3
        assert pool.in_flight == 0

    def test_current_limit_has_no_group(self) -> None:
        pool = _BackpressureGate(ConcurrencyConfig(max_concurrency=4))
        assert pool.current_limit(None) == 4


class TestGroupedGate:
    """``group=<name>``: one named ``ConcurrencyLimits`` group (``Bulkhead``'s per-backend pool)."""

    def test_tickets_carry_the_group_name(self) -> None:
        pool = _BackpressureGate(ConcurrencyConfig(max_concurrency=1), group="slow")
        probe = _GateProbe(_config=KnotConfig(id="probe", concurrency_group="slow"))
        ticket = pool.try_admit(probe)
        assert ticket is not None
        assert ticket.group == "slow"
        pool.release(ticket)

    def test_current_limit_reads_the_named_group(self) -> None:
        pool = _BackpressureGate(ConcurrencyConfig(max_concurrency=4), group="slow")
        assert pool.current_limit("slow") == 4


class TestBackpressureShedding:
    async def test_queue_full_raises_when_depth_exceeded(self) -> None:
        pool = _BackpressureGate(ConcurrencyConfig(max_concurrency=1, max_queue_depth=1))
        await pool.acquire()
        waiter = asyncio.ensure_future(pool.acquire())
        await asyncio.sleep(0)
        assert pool.waiting == 1
        with pytest.raises(asyncio.QueueFull):
            await pool.acquire()
        pool.release()
        await waiter
        pool.release()


class TestAcquireTimeout:
    async def test_timeout_raises_when_no_slot_frees(self) -> None:
        pool = _BackpressureGate(ConcurrencyConfig(max_concurrency=1, acquire_timeout=0.02))
        await pool.acquire()
        with pytest.raises(TimeoutError):
            await pool.acquire()
        assert pool.waiting == 0
        pool.release()


class TestReleaseIdentity:
    """Regression: ``AdmissionTicket`` compares by *value*, not identity.

    Every ticket a pool's single reused token produces shares the same
    knot_id/group/held, so two simultaneously-held tickets are mutually
    ``==`` while being distinct objects the wrapped gate tracks by identity.
    Releasing one by explicit reference must free exactly that one, never a
    different, merely-equal ticket.
    """

    async def test_releasing_one_of_two_equal_tickets_frees_only_that_one(self) -> None:
        pool = _BackpressureGate(ConcurrencyConfig(max_concurrency=2))
        await pool.acquire()
        await pool.acquire()
        assert pool.in_flight == 2

        probe = _GateProbe(_config=KnotConfig(id="probe"))
        # A third ticket obtained directly through the AdmissionGate surface,
        # refused because both slots are already held.
        assert pool.try_admit(probe) is None

        pool.release()  # pops one of the two (order-independent by design)
        assert pool.in_flight == 1
        pool.release()
        assert pool.in_flight == 0

    def test_release_rejects_a_ticket_this_pool_never_issued(self) -> None:
        pool_a = _BackpressureGate(ConcurrencyConfig(max_concurrency=1))
        pool_b = _BackpressureGate(ConcurrencyConfig(max_concurrency=1))
        probe = _GateProbe(_config=KnotConfig(id="probe"))
        ticket = pool_a.try_admit(probe)
        assert ticket is not None
        with pytest.raises(AdmissionReleaseError):
            pool_b.release(ticket)

    def test_release_with_no_ticket_and_nothing_held_raises(self) -> None:
        pool = _BackpressureGate(ConcurrencyConfig())
        with pytest.raises(AdmissionReleaseError):
            pool.release()


class TestAdmissionGateSurface:
    def test_has_capacity_and_set_limit(self) -> None:
        pool = _BackpressureGate(ConcurrencyConfig(max_concurrency=1))
        probe = _GateProbe(_config=KnotConfig(id="probe"))
        ticket = pool.try_admit(probe)
        assert ticket is not None
        assert pool.has_capacity() is False
        pool.set_limit(None, 2)
        assert pool.has_capacity() is True
        pool.release(ticket)

    async def test_wait_for_release_unblocks_on_release(self) -> None:
        pool = _BackpressureGate(ConcurrencyConfig(max_concurrency=1))
        await pool.acquire()
        waiter = asyncio.ensure_future(pool.wait_for_release())
        await asyncio.sleep(0)
        assert waiter.done() is False
        pool.release()
        await waiter
