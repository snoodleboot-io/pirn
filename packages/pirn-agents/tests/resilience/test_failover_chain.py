"""Mirrored tests for the failover routing chain (PIR-496 / S2).

Uses stub async operations and a manual clock so timeouts and circuit-open skips
are deterministic. Verifies the chain stops at the first success, records a
trace of attempts and reasons, honours per-candidate timeouts, and skips
candidates whose breaker is open.
"""

from __future__ import annotations

import asyncio

import pytest
from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.tapestry import Tapestry

from pirn_agents.resilience.circuit_breaker_config import CircuitBreakerConfig
from pirn_agents.resilience.circuit_breaker_registry import CircuitBreakerRegistry
from pirn_agents.resilience.failover_candidate import FailoverCandidate
from pirn_agents.resilience.failover_chain import FailoverChain


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
    async def test_rejects_empty(self) -> None:
        with Tapestry():
            chain = FailoverChain(candidates=[], _config=KnotConfig(id="failover"))
        with pytest.raises(ValueError, match="non-empty"):
            await chain.process(candidates=[])

    async def test_rejects_non_candidate(self) -> None:
        # The framework validates a literal (non-Knot) constructor value
        # against its declared type eagerly, at construction time, so the
        # bad entry never reaches process().
        with Tapestry(), pytest.raises(TypeError, match="FailoverCandidate"):
            FailoverChain(candidates=[object()], _config=KnotConfig(id="failover"))  # type: ignore[list-item]

    async def test_rejects_bad_breakers(self) -> None:
        with Tapestry():
            chain = FailoverChain(
                candidates=[FailoverCandidate("a", _ok(1))],
                breakers=object(),  # type: ignore[arg-type]
                _config=KnotConfig(id="failover"),
            )
        with pytest.raises(TypeError, match="CircuitBreakerRegistry"):
            await chain.process(
                candidates=[FailoverCandidate("a", _ok(1))],
                breakers=object(),  # type: ignore[arg-type]
            )


class TestOrdering:
    async def test_first_success_wins_and_stops(self) -> None:
        with Tapestry() as t:
            FailoverChain(
                candidates=[
                    FailoverCandidate("primary", _ok("A")),
                    FailoverCandidate("secondary", _ok("B")),
                ],
                _config=KnotConfig(id="failover"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["failover"]
        assert result.succeeded is True
        assert result.chosen == "primary"
        assert result.value == "A"
        assert [a.name for a in result.attempts] == ["primary"]

    async def test_falls_through_error_to_next(self) -> None:
        with Tapestry() as t:
            FailoverChain(
                candidates=[
                    FailoverCandidate("primary", _boom("down")),
                    FailoverCandidate("secondary", _ok("B")),
                ],
                _config=KnotConfig(id="failover"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["failover"]
        assert result.chosen == "secondary"
        assert result.value == "B"
        assert isinstance(result.attempts[0].result, Err)
        assert result.attempts[0].result.record.message == "down"
        assert isinstance(result.attempts[1].result, Ok)

    async def test_all_fail_returns_exhausted_trace(self) -> None:
        with Tapestry() as t:
            FailoverChain(
                candidates=[
                    FailoverCandidate("a", _boom("x")),
                    FailoverCandidate("b", _boom("y")),
                ],
                _config=KnotConfig(id="failover"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["failover"]
        assert result.succeeded is False
        assert result.chosen is None
        assert result.value is None
        assert [isinstance(a.result, Err) for a in result.attempts] == [True, True]


class TestTimeout:
    async def test_per_candidate_timeout_reroutes(self) -> None:
        with Tapestry() as t:
            FailoverChain(
                candidates=[
                    FailoverCandidate("slow", _hang(), timeout=0.01),
                    FailoverCandidate("fast", _ok("B")),
                ],
                _config=KnotConfig(id="failover"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["failover"]
        assert result.chosen == "fast"
        assert isinstance(result.attempts[0].result, Err)
        assert result.attempts[0].result.record.exc_type == "TimeoutError"


class TestCircuitIntegration:
    async def test_skips_open_candidate(self) -> None:
        breakers = CircuitBreakerRegistry(CircuitBreakerConfig(failure_threshold=1))
        await breakers.get("primary").record_failure()  # trip it OPEN
        with Tapestry() as t:
            FailoverChain(
                candidates=[
                    FailoverCandidate("primary", _ok("A")),
                    FailoverCandidate("secondary", _ok("B")),
                ],
                breakers=breakers,
                _config=KnotConfig(id="failover"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["failover"]
        assert result.chosen == "secondary"
        assert isinstance(result.attempts[0].result, Skipped)

    async def test_repeated_failure_trips_breaker_across_runs(self) -> None:
        breakers = CircuitBreakerRegistry(CircuitBreakerConfig(failure_threshold=1))
        candidates = [
            FailoverCandidate("primary", _boom("down")),
            FailoverCandidate("secondary", _ok("B")),
        ]
        with Tapestry() as t1:
            FailoverChain(
                candidates=candidates, breakers=breakers, _config=KnotConfig(id="failover")
            )
        first_run = await t1.run(RunRequest())
        assert first_run.succeeded
        first = first_run.outputs["failover"]
        assert isinstance(first.attempts[0].result, Err)
        # Second run: primary's breaker is now open, so it is skipped.
        with Tapestry() as t2:
            FailoverChain(
                candidates=candidates, breakers=breakers, _config=KnotConfig(id="failover")
            )
        second_run = await t2.run(RunRequest())
        assert second_run.succeeded
        second = second_run.outputs["failover"]
        assert isinstance(second.attempts[0].result, Skipped)

    async def test_success_records_into_breaker(self) -> None:
        breakers = CircuitBreakerRegistry(CircuitBreakerConfig(failure_threshold=2))
        with Tapestry() as t:
            FailoverChain(
                candidates=[FailoverCandidate("p", _ok("A"))],
                breakers=breakers,
                _config=KnotConfig(id="failover"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["failover"]
        assert result.succeeded is True
        # A recorded success keeps the breaker closed.
        assert breakers.get("p").state.value == "closed"
