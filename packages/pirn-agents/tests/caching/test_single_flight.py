"""Mirrored tests for :class:`SingleFlight` request coalescing (PIR-507).

A gate event holds the leader mid-flight so both callers are provably concurrent
before it resolves — the coalescing behaviour is deterministic, no sleeps-race.
"""

from __future__ import annotations

import asyncio

import pytest

from pirn_agents.caching.single_flight import SingleFlight


class TestCoalescing:
    async def test_concurrent_identical_calls_run_factory_once(self) -> None:
        flight = SingleFlight()
        gate = asyncio.Event()
        calls = 0

        async def factory() -> str:
            nonlocal calls
            calls += 1
            await gate.wait()
            return "shared"

        first = asyncio.ensure_future(flight.run("k", factory))
        second = asyncio.ensure_future(flight.run("k", factory))
        await asyncio.sleep(0)  # let both attach to the same in-flight future
        await asyncio.sleep(0)
        gate.set()

        results = await asyncio.gather(first, second)
        assert results == ["shared", "shared"]
        assert calls == 1  # only the leader hit the provider
        assert flight.coalesced == 1

    async def test_shared_error_propagates_to_all_waiters(self) -> None:
        flight = SingleFlight()
        gate = asyncio.Event()

        async def factory() -> str:
            await gate.wait()
            raise RuntimeError("boom")

        first = asyncio.ensure_future(flight.run("k", factory))
        second = asyncio.ensure_future(flight.run("k", factory))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        gate.set()

        results = await asyncio.gather(first, second, return_exceptions=True)
        assert all(isinstance(r, RuntimeError) for r in results)
        assert all(str(r) == "boom" for r in results)


class TestSingleCallerUnchanged:
    async def test_key_cleared_after_resolution(self) -> None:
        flight = SingleFlight()
        calls = 0

        async def factory() -> int:
            nonlocal calls
            calls += 1
            return calls

        first = await flight.run("k", factory)
        second = await flight.run("k", factory)  # sequential: not coalesced

        assert (first, second) == (1, 2)
        assert flight.coalesced == 0  # no concurrent overlap
        assert len(flight) == 0  # nothing left in flight

    async def test_distinct_keys_do_not_coalesce(self) -> None:
        flight = SingleFlight()
        gate = asyncio.Event()
        calls = 0

        async def factory() -> str:
            nonlocal calls
            calls += 1
            await gate.wait()
            return "v"

        a = asyncio.ensure_future(flight.run("a", factory))
        b = asyncio.ensure_future(flight.run("b", factory))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        gate.set()

        await asyncio.gather(a, b)
        assert calls == 2  # different keys each run
        assert flight.coalesced == 0

    async def test_error_clears_key_for_retry(self) -> None:
        flight = SingleFlight()

        async def failing() -> str:
            raise ValueError("nope")

        with pytest.raises(ValueError, match="nope"):
            await flight.run("k", failing)
        assert len(flight) == 0  # key cleared so a retry can proceed
