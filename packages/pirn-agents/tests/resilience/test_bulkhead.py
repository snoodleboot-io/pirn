"""Mirrored tests for per-backend bulkhead isolation (PIR-503 / S4).

Verifies each backend gets its own bounded pool, that saturating one backend
does not block or starve another, that per-backend override sizes apply, and
that the default pool covers un-named backends.
"""

from __future__ import annotations

import asyncio

import pytest

from pirn_agents.performance.concurrency_config import ConcurrencyConfig
from pirn_agents.resilience.bulkhead import Bulkhead
from pirn_agents.resilience.bulkhead_config import BulkheadConfig


class TestConstruction:
    def test_rejects_bad_config(self) -> None:
        with pytest.raises(TypeError, match="BulkheadConfig"):
            Bulkhead(object())  # type: ignore[arg-type]

    def test_default_config_when_none(self) -> None:
        bulkhead = Bulkhead()
        assert bulkhead.backends() == ()


class TestPoolSizing:
    async def test_override_bounds_named_backend(self) -> None:
        config = BulkheadConfig(
            default=ConcurrencyConfig(max_concurrency=8),
            overrides={"slow": ConcurrencyConfig(max_concurrency=2)},
        )
        bulkhead = Bulkhead(config)
        peak = 0
        live = 0
        lock = asyncio.Lock()

        async def worker() -> None:
            nonlocal peak, live
            async with bulkhead.slot("slow"):
                async with lock:
                    live += 1
                    peak = max(peak, live)
                await asyncio.sleep(0.02)
                async with lock:
                    live -= 1

        await asyncio.gather(*(worker() for _ in range(6)))
        assert peak <= 2
        assert bulkhead.in_flight("slow") == 0

    async def test_default_applies_to_unnamed_backend(self) -> None:
        bulkhead = Bulkhead(BulkheadConfig(default=ConcurrencyConfig(max_concurrency=1)))
        # An un-named backend falls back to the default one-slot pool.
        async with bulkhead.slot("anything"):
            assert bulkhead.in_flight("anything") == 1
        assert bulkhead.in_flight("anything") == 0


class TestIsolation:
    async def test_saturating_one_backend_does_not_block_another(self) -> None:
        config = BulkheadConfig(
            overrides={
                "busy": ConcurrencyConfig(max_concurrency=1),
                "free": ConcurrencyConfig(max_concurrency=1),
            }
        )
        bulkhead = Bulkhead(config)

        # Saturate "busy" and park a waiter on it.
        async with bulkhead.slot("busy"):
            parked = asyncio.ensure_future(_hold(bulkhead, "busy"))
            await asyncio.sleep(0)
            assert bulkhead.waiting("busy") == 1  # busy pool is saturated

            # "free" is unaffected: a call to it acquires immediately.
            ran = False
            async with bulkhead.slot("free"):
                ran = True
            assert ran is True
            assert bulkhead.in_flight("free") == 0

        await parked  # let the parked "busy" waiter complete

    async def test_distinct_backends_get_distinct_pools(self) -> None:
        bulkhead = Bulkhead()
        async with bulkhead.slot("a"):
            async with bulkhead.slot("b"):
                assert set(bulkhead.backends()) == {"a", "b"}
                assert bulkhead.in_flight("a") == 1
                assert bulkhead.in_flight("b") == 1


async def _hold(bulkhead: Bulkhead, backend: str) -> None:
    async with bulkhead.slot(backend):
        await asyncio.sleep(0)
