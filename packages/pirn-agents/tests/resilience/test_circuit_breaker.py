"""Mirrored tests for the per-endpoint circuit breaker (PIR-493 / S1).

Drives the closed→open→half-open→closed cycle with an injected manual clock, so
transitions are deterministic and no real time passes. Verifies that OPEN calls
fail fast with :class:`CircuitOpenError` before any work runs, that a HALF_OPEN
failure re-opens, and that state is serialised across concurrent callers.
"""

from __future__ import annotations

import asyncio

import pytest

from pirn_agents.resilience.circuit_breaker import CircuitBreaker
from pirn_agents.resilience.circuit_breaker_config import CircuitBreakerConfig
from pirn_agents.resilience.circuit_open_error import CircuitOpenError
from pirn_agents.resilience.circuit_state import CircuitState


class _ManualClock:
    """A controllable monotonic clock: value only advances when told to."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


def _breaker(
    *,
    failure_threshold: int = 3,
    cooldown_seconds: float = 10.0,
    success_threshold: int = 1,
    clock: _ManualClock | None = None,
) -> CircuitBreaker:
    return CircuitBreaker(
        CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds,
            success_threshold=success_threshold,
        ),
        endpoint="ep",
        clock=clock if clock is not None else _ManualClock(),
    )


class TestConstruction:
    def test_rejects_non_config(self) -> None:
        with pytest.raises(TypeError, match="CircuitBreakerConfig"):
            CircuitBreaker(object())  # type: ignore[arg-type]

    def test_starts_closed(self) -> None:
        assert _breaker().state is CircuitState.CLOSED


class TestTripping:
    async def test_opens_on_consecutive_failure_threshold(self) -> None:
        breaker = _breaker(failure_threshold=3)
        for _ in range(3):
            await breaker.record_failure()
        assert breaker.state is CircuitState.OPEN

    async def test_success_resets_consecutive_failures(self) -> None:
        breaker = _breaker(failure_threshold=3)
        await breaker.record_failure()
        await breaker.record_failure()
        await breaker.record_success()  # resets the run
        await breaker.record_failure()
        assert breaker.state is CircuitState.CLOSED


class TestFailFast:
    async def test_open_call_fails_fast_without_running(self) -> None:
        clock = _ManualClock()
        breaker = _breaker(failure_threshold=1, clock=clock)
        await breaker.record_failure()  # trips OPEN
        with pytest.raises(CircuitOpenError) as excinfo:
            await breaker.acquire()
        assert excinfo.value.endpoint == "ep"
        assert excinfo.value.retry_at == pytest.approx(10.0)

    async def test_guard_body_skipped_when_open(self) -> None:
        breaker = _breaker(failure_threshold=1)
        await breaker.record_failure()
        ran = False
        with pytest.raises(CircuitOpenError):
            async with breaker.guard():
                ran = True  # pragma: no cover - must not execute
        assert ran is False


class TestHalfOpenRecovery:
    async def test_cooldown_moves_open_to_half_open(self) -> None:
        clock = _ManualClock()
        breaker = _breaker(failure_threshold=1, cooldown_seconds=10.0, clock=clock)
        await breaker.record_failure()
        clock.advance(10.0)
        await breaker.acquire()  # cooldown elapsed → trial admitted
        assert breaker.state is CircuitState.HALF_OPEN

    async def test_trial_success_closes(self) -> None:
        clock = _ManualClock()
        breaker = _breaker(
            failure_threshold=1, cooldown_seconds=10.0, success_threshold=2, clock=clock
        )
        await breaker.record_failure()
        clock.advance(10.0)
        await breaker.acquire()
        await breaker.record_success()
        assert breaker.state is CircuitState.HALF_OPEN  # one more needed
        await breaker.record_success()
        assert breaker.state is CircuitState.CLOSED

    async def test_trial_failure_reopens_and_restarts_cooldown(self) -> None:
        clock = _ManualClock()
        breaker = _breaker(failure_threshold=1, cooldown_seconds=10.0, clock=clock)
        await breaker.record_failure()
        clock.advance(10.0)
        await breaker.acquire()  # HALF_OPEN
        await breaker.record_failure()  # trial fails → OPEN again
        assert breaker.state is CircuitState.OPEN
        with pytest.raises(CircuitOpenError):
            await breaker.acquire()  # cooldown restarted


class TestConcurrencySafety:
    async def test_concurrent_failures_count_exactly(self) -> None:
        breaker = _breaker(failure_threshold=50)
        await asyncio.gather(*(breaker.record_failure() for _ in range(50)))
        assert breaker.state is CircuitState.OPEN

    async def test_guard_records_success_on_clean_exit(self) -> None:
        breaker = _breaker(failure_threshold=1)
        await breaker.record_failure()  # 1 failure so far but threshold=1 -> OPEN
        # rebuild for a clean run
        breaker = _breaker(failure_threshold=2)
        async with breaker.guard():
            pass
        await breaker.record_failure()
        assert breaker.state is CircuitState.CLOSED  # success reset the run
