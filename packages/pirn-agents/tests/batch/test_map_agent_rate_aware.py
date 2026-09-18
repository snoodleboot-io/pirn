"""Rate-aware adaptive scheduling tests for ``MapAgent`` (ADR agents-speaks-core, WS4b).

The shared :class:`TokenBucketRateLimiter` and provider-neutral
:class:`RateLimitSignal` are unchanged. What changed is how a throttle
reaches the concurrency governor: ``AdaptiveConcurrencyController`` is now
an ``AdmissionObserver`` (see its module docstring), reacting to
``on_throttle`` (called directly by the per-item knot on a
``RateLimitSignal``) and ``on_release`` (called by the engine on every
item's settle). A manual clock plus a fake sleep still make the rate
limiter's own pacing deterministic — no real elapsed time — but the retry
backoff itself is the engine's (``GovernedDispatch``), which sleeps for real
(kept short with ``base_delay`` near zero) rather than through an injectable
hook, since the engine owns the retry loop now.
"""

from __future__ import annotations

import asyncio

import pytest
from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig

from pirn_agents.batch.adaptive_concurrency_controller import AdaptiveConcurrencyController
from pirn_agents.batch.map_agent import MapAgent
from pirn_agents.batch.rate_limit_signal import RateLimitSignal
from pirn_agents.resilience.rate_limiter_config import RateLimiterConfig
from pirn_agents.resilience.token_bucket_rate_limiter import TokenBucketRateLimiter
from tests.batch.batch_doubles import InFlightCounter, StubAgent, gated_agent


class _ManualClock:
    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class _AdvancingSleep:
    """A fake async sleep that advances a manual clock instead of blocking."""

    def __init__(self, clock: _ManualClock) -> None:
        self._clock = clock
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        self._clock.advance(seconds)


async def _drain(runner: MapAgent, inputs: object) -> list:
    return [result async for result in runner.run(inputs)]


async def test_rate_limiter_paces_dispatch() -> None:
    clock = _ManualClock()
    sleep = _AdvancingSleep(clock)
    limiter = TokenBucketRateLimiter(
        RateLimiterConfig(refill_rate=1.0, capacity=1.0), clock=clock, sleep=sleep
    )
    runner = MapAgent(
        run_item=StubAgent(),
        _config=KnotConfig(id="map-agent"),
        batch_id="r1",
        concurrency=4,
        rate_limiter=limiter,
    )

    results = await _drain(runner, ["a", "b", "c"])

    # One token to start; each further attempt waits a full refill second.
    assert all(r.succeeded for r in results)
    assert len(sleep.calls) >= 2


async def test_throttle_scales_down_and_pauses_bucket() -> None:
    clock = _ManualClock()
    sleep = _AdvancingSleep(clock)
    limiter = TokenBucketRateLimiter(
        RateLimiterConfig(refill_rate=100.0, capacity=100.0), clock=clock, sleep=sleep
    )
    controller = AdaptiveConcurrencyController(min_limit=1, max_limit=4, initial=4)

    state = {"throttled": False}

    async def agent(item: object) -> object:
        if not state["throttled"]:
            state["throttled"] = True
            raise RateLimitSignal(retry_after=0.01)
        return f"done:{item}"

    runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        batch_id="r2",
        concurrency=4,
        retries=1,
        rate_limiter=limiter,
        concurrency_controller=controller,
    )

    results = await _drain(runner, ["x"])

    assert results[0].succeeded
    # Throttle backed the controller off (4 -> 2) then one successful release
    # bumped it (-> 3).
    assert controller.limit() == 3
    # The retry's own attempt also honoured the 5s-shaped Retry-After via the
    # shared bucket's pause (a small value here so the test stays fast).
    assert 0.01 in sleep.calls


async def test_throttle_without_retry_reports_error() -> None:
    controller = AdaptiveConcurrencyController(min_limit=1, max_limit=4, initial=4)

    async def agent(item: object) -> object:
        raise RateLimitSignal(retry_after=1.0, message="429 slow down")

    runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        batch_id="r3",
        concurrency=4,
        retries=0,
        concurrency_controller=controller,
    )

    results = await _drain(runner, ["x"])

    assert isinstance(results[0].outcome, Err)
    assert results[0].error is not None and "slow down" in results[0].error
    assert controller.limit() == 2  # scaled down even though the item failed


async def test_adaptive_limit_caps_in_flight() -> None:
    counter = InFlightCounter()
    gate = asyncio.Event()
    controller = AdaptiveConcurrencyController(min_limit=1, max_limit=2, initial=2)
    runner = MapAgent(
        run_item=gated_agent(gate, counter),
        _config=KnotConfig(id="map-agent"),
        batch_id="r4",
        concurrency=8,
        concurrency_controller=controller,
    )

    task = asyncio.ensure_future(_drain(runner, list(range(6))))
    for _ in range(50):
        await asyncio.sleep(0)
    assert counter.peak == 2  # controller's initial limit wins over concurrency=8
    gate.set()
    await task


def test_rejects_wrong_rate_limiter_type() -> None:
    with pytest.raises(TypeError):
        MapAgent(
            run_item=StubAgent(), _config=KnotConfig(id="map-agent"), rate_limiter="not-a-limiter"
        )


def test_rejects_wrong_controller_type() -> None:
    with pytest.raises(TypeError):
        MapAgent(
            run_item=StubAgent(), _config=KnotConfig(id="map-agent"), concurrency_controller="nope"
        )


def test_rate_limit_signal_rejects_negative_retry_after() -> None:
    with pytest.raises(ValueError):
        RateLimitSignal(retry_after=-1.0)
