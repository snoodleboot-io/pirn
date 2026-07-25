"""Mirrored tests for the failover routing chain (PIR-496 / S2).

Uses stub async operations and a manual clock so timeouts and circuit-open skips
are deterministic. Verifies the chain stops at the first success, records a
trace of attempts and reasons, honours per-candidate timeouts, and skips
candidates whose breaker is open.
"""

from __future__ import annotations

import asyncio

import pytest

from pirn_agents.resilience.circuit_breaker_config import CircuitBreakerConfig
from pirn_agents.resilience.circuit_breaker_registry import CircuitBreakerRegistry
from pirn_agents.resilience.failover_candidate import FailoverCandidate
from pirn_agents.resilience.failover_chain import FailoverChain
from pirn_agents.resilience.failover_outcome import FailoverOutcome


def _ok(value: object):
    async def _op() -> object:
        return value

    return _op


def _boom(message: str):
    async def _op() -> object:
        raise RuntimeError(message)

    return _op


def _hang():
    async def _op() -> object:
        await asyncio.sleep(3600)
        return "never"  # pragma: no cover

    return _op


class TestConstruction:
    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            FailoverChain([])

    def test_rejects_non_candidate(self) -> None:
        with pytest.raises(TypeError, match="FailoverCandidate"):
            FailoverChain([object()])  # type: ignore[list-item]

    def test_rejects_bad_breakers(self) -> None:
        with pytest.raises(TypeError, match="CircuitBreakerRegistry"):
            FailoverChain([FailoverCandidate("a", _ok(1))], breakers=object())  # type: ignore[arg-type]


class TestOrdering:
    async def test_first_success_wins_and_stops(self) -> None:
        chain = FailoverChain(
            [
                FailoverCandidate("primary", _ok("A")),
                FailoverCandidate("secondary", _ok("B")),
            ]
        )
        result = await chain.run()
        assert result.succeeded is True
        assert result.chosen == "primary"
        assert result.value == "A"
        assert [a.name for a in result.attempts] == ["primary"]

    async def test_falls_through_error_to_next(self) -> None:
        chain = FailoverChain(
            [
                FailoverCandidate("primary", _boom("down")),
                FailoverCandidate("secondary", _ok("B")),
            ]
        )
        result = await chain.run()
        assert result.chosen == "secondary"
        assert result.value == "B"
        assert result.attempts[0].outcome is FailoverOutcome.ERROR
        assert result.attempts[0].error == "down"
        assert result.attempts[1].outcome is FailoverOutcome.SUCCESS

    async def test_all_fail_returns_exhausted_trace(self) -> None:
        chain = FailoverChain(
            [
                FailoverCandidate("a", _boom("x")),
                FailoverCandidate("b", _boom("y")),
            ]
        )
        result = await chain.run()
        assert result.succeeded is False
        assert result.chosen is None
        assert result.value is None
        assert [a.outcome for a in result.attempts] == [
            FailoverOutcome.ERROR,
            FailoverOutcome.ERROR,
        ]


class TestTimeout:
    async def test_per_candidate_timeout_reroutes(self) -> None:
        chain = FailoverChain(
            [
                FailoverCandidate("slow", _hang(), timeout=0.01),
                FailoverCandidate("fast", _ok("B")),
            ]
        )
        result = await chain.run()
        assert result.chosen == "fast"
        assert result.attempts[0].outcome is FailoverOutcome.TIMEOUT


class TestCircuitIntegration:
    async def test_skips_open_candidate(self) -> None:
        breakers = CircuitBreakerRegistry(CircuitBreakerConfig(failure_threshold=1))
        await breakers.get("primary").record_failure()  # trip it OPEN
        chain = FailoverChain(
            [
                FailoverCandidate("primary", _ok("A")),
                FailoverCandidate("secondary", _ok("B")),
            ],
            breakers=breakers,
        )
        result = await chain.run()
        assert result.chosen == "secondary"
        assert result.attempts[0].outcome is FailoverOutcome.CIRCUIT_OPEN

    async def test_repeated_failure_trips_breaker_across_runs(self) -> None:
        breakers = CircuitBreakerRegistry(CircuitBreakerConfig(failure_threshold=1))
        candidates = [
            FailoverCandidate("primary", _boom("down")),
            FailoverCandidate("secondary", _ok("B")),
        ]
        first = await FailoverChain(candidates, breakers=breakers).run()
        assert first.attempts[0].outcome is FailoverOutcome.ERROR
        # Second run: primary's breaker is now open, so it is skipped.
        second = await FailoverChain(candidates, breakers=breakers).run()
        assert second.attempts[0].outcome is FailoverOutcome.CIRCUIT_OPEN

    async def test_success_records_into_breaker(self) -> None:
        breakers = CircuitBreakerRegistry(CircuitBreakerConfig(failure_threshold=2))
        chain = FailoverChain([FailoverCandidate("p", _ok("A"))], breakers=breakers)
        result = await chain.run()
        assert result.succeeded is True
        # A recorded success keeps the breaker closed.
        assert breakers.get("p").state.value == "closed"
