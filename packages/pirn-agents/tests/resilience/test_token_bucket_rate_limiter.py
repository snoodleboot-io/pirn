"""Mirrored tests for the shared async token-bucket limiter (PIR-499 / S3).

A manual clock plus a fake sleep that advances that clock make refills and waits
deterministic — no real elapsed time. Verifies burst capacity, that a depleted
bucket makes callers wait for a refill (yielding, not busy-polling), that
``Retry-After`` pauses acquisition, and that one bucket is shared across callers.
"""

from __future__ import annotations

import pytest

from pirn_agents.resilience.rate_limiter_config import RateLimiterConfig
from pirn_agents.resilience.token_bucket_rate_limiter import TokenBucketRateLimiter


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


def _limiter(
    refill_rate: float, capacity: float, clock: _ManualClock
) -> tuple[TokenBucketRateLimiter, _AdvancingSleep]:
    sleep = _AdvancingSleep(clock)
    limiter = TokenBucketRateLimiter(
        RateLimiterConfig(refill_rate=refill_rate, capacity=capacity),
        clock=clock,
        sleep=sleep,
    )
    return limiter, sleep


class TestConstruction:
    def test_rejects_non_config(self) -> None:
        with pytest.raises(TypeError, match="RateLimiterConfig"):
            TokenBucketRateLimiter(object())  # type: ignore[arg-type]

    def test_starts_full(self) -> None:
        clock = _ManualClock()
        limiter, _ = _limiter(1.0, 5.0, clock)
        assert limiter.available_tokens == 5.0


class TestBurst:
    async def test_burst_up_to_capacity_without_waiting(self) -> None:
        clock = _ManualClock()
        limiter, sleep = _limiter(1.0, 3.0, clock)
        for _ in range(3):
            await limiter.acquire()
        assert sleep.calls == []  # no waiting within capacity
        assert limiter.available_tokens == pytest.approx(0.0)

    async def test_rejects_request_over_capacity(self) -> None:
        clock = _ManualClock()
        limiter, _ = _limiter(1.0, 3.0, clock)
        with pytest.raises(ValueError, match="exceeds capacity"):
            await limiter.acquire(4.0)

    async def test_rejects_non_positive(self) -> None:
        clock = _ManualClock()
        limiter, _ = _limiter(1.0, 3.0, clock)
        with pytest.raises(ValueError, match="positive"):
            await limiter.acquire(0)


class TestWaiting:
    async def test_depleted_bucket_waits_for_refill(self) -> None:
        clock = _ManualClock()
        limiter, sleep = _limiter(refill_rate=2.0, capacity=1.0, clock=clock)
        await limiter.acquire()  # empties the bucket, no wait
        await limiter.acquire()  # must wait for 1 token at 2/s -> 0.5s
        assert sleep.calls == [pytest.approx(0.5)]
        assert clock() == pytest.approx(0.5)

    async def test_partial_tokens_only_wait_for_deficit(self) -> None:
        clock = _ManualClock()
        limiter, sleep = _limiter(refill_rate=1.0, capacity=10.0, clock=clock)
        await limiter.acquire(10.0)  # empty
        clock.advance(4.0)  # 4 tokens accrue
        await limiter.acquire(5.0)  # need 1 more -> 1.0s wait
        assert sleep.calls == [pytest.approx(1.0)]


class TestRetryAfter:
    async def test_pause_blocks_until_elapsed(self) -> None:
        clock = _ManualClock()
        limiter, sleep = _limiter(refill_rate=100.0, capacity=100.0, clock=clock)
        limiter.pause_for(2.0)  # upstream Retry-After: 2s
        await limiter.acquire()  # tokens exist, but pause forces a wait first
        assert sleep.calls == [pytest.approx(2.0)]
        assert clock() == pytest.approx(2.0)

    def test_pause_rejects_negative(self) -> None:
        clock = _ManualClock()
        limiter, _ = _limiter(1.0, 1.0, clock)
        with pytest.raises(ValueError, match="non-negative"):
            limiter.pause_for(-1.0)

    async def test_overlapping_pause_extends_to_latest(self) -> None:
        clock = _ManualClock()
        limiter, _ = _limiter(refill_rate=100.0, capacity=100.0, clock=clock)
        limiter.pause_for(5.0)
        limiter.pause_for(2.0)  # shorter — must not shorten the existing pause
        await limiter.acquire()
        assert clock() == pytest.approx(5.0)


class TestSharedBucket:
    async def test_two_callers_share_one_bucket(self) -> None:
        clock = _ManualClock()
        limiter, sleep = _limiter(refill_rate=1.0, capacity=1.0, clock=clock)
        # One token total; two sequential acquires draw from the same bucket, so
        # the second must wait a full second for a refill.
        await limiter.acquire()
        await limiter.acquire()
        assert sleep.calls == [pytest.approx(1.0)]
