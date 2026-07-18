"""F28-S2 tests: MapAgent's rate-aware adaptive scheduling over reused F21 infra.

A manual clock plus a fake sleep that advances it make the shared
:class:`TokenBucketRateLimiter` deterministic — no real elapsed time. The
provider throttle is modelled provider-neutrally as a :class:`RateLimitSignal`
the ``run_item`` adapter raises.
"""

from __future__ import annotations

import asyncio

import pytest

from pirn_agents.batch.adaptive_concurrency_controller import AdaptiveConcurrencyController
from pirn_agents.batch.batch_item_status import BatchItemStatus
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
    return [result async for result in runner.run(inputs)]  # type: ignore[arg-type]


async def test_rate_limiter_paces_dispatch() -> None:
    clock = _ManualClock()
    sleep = _AdvancingSleep(clock)
    limiter = TokenBucketRateLimiter(
        RateLimiterConfig(refill_rate=1.0, capacity=1.0), clock=clock, sleep=sleep
    )
    runner = MapAgent(StubAgent(), concurrency=4, rate_limiter=limiter)

    results = await _drain(runner, ["a", "b", "c"])

    # One token to start; each further attempt waits a full refill second.
    assert all(r.status is BatchItemStatus.OK for r in results)
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
            raise RateLimitSignal(retry_after=5.0)
        return f"done:{item}"

    runner = MapAgent(
        agent,
        concurrency=4,
        retries=1,
        rate_limiter=limiter,
        concurrency_controller=controller,
    )

    results = await _drain(runner, ["x"])

    assert results[0].status is BatchItemStatus.OK
    assert results[0].attempts == 2
    # Throttle backed the controller off (4 -> 2) then one success bumped it (-> 3).
    assert controller.limit() == 3
    # The retry honoured the 5s Retry-After via the shared bucket's pause.
    assert 5.0 in sleep.calls


async def test_throttle_without_retry_reports_error() -> None:
    controller = AdaptiveConcurrencyController(min_limit=1, max_limit=4, initial=4)

    async def agent(item: object) -> object:
        raise RateLimitSignal(retry_after=1.0, message="429 slow down")

    runner = MapAgent(agent, concurrency=4, retries=0, concurrency_controller=controller)

    results = await _drain(runner, ["x"])

    assert results[0].status is BatchItemStatus.ERROR
    assert results[0].error is not None and "slow down" in results[0].error
    assert controller.limit() == 2  # scaled down even though the item failed


async def test_adaptive_limit_caps_in_flight() -> None:
    counter = InFlightCounter()
    gate = asyncio.Event()
    controller = AdaptiveConcurrencyController(min_limit=1, max_limit=2, initial=2)
    runner = MapAgent(gated_agent(gate, counter), concurrency=8, concurrency_controller=controller)

    task = asyncio.ensure_future(_drain(runner, list(range(6))))
    for _ in range(20):
        await asyncio.sleep(0)
    assert counter.peak == 2  # controller cap wins over the higher concurrency
    gate.set()
    await task


def test_rejects_wrong_rate_limiter_type() -> None:
    with pytest.raises(TypeError):
        MapAgent(StubAgent(), rate_limiter="not-a-limiter")  # type: ignore[arg-type]


def test_rejects_wrong_controller_type() -> None:
    with pytest.raises(TypeError):
        MapAgent(StubAgent(), concurrency_controller="nope")  # type: ignore[arg-type]


def test_rate_limit_signal_rejects_negative_retry_after() -> None:
    with pytest.raises(ValueError):
        RateLimitSignal(retry_after=-1.0)
