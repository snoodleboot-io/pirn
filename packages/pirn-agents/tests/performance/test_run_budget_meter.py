"""Mirrored tests for :class:`RunBudgetMeter` breach + cancellation paths (PIR-280).

Exercises iteration, token, and deadline breach scenarios and confirms that a
breach flips the shared cancellation token *and* raises the typed
:class:`BudgetBreachError`, leaving the meter's counters intact (no partial
state corruption) so a caller can build a clean terminal result.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest

from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.performance.budget_limit import BudgetLimit
from pirn_agents.performance.cancellation_token import CancellationToken
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.tool import Tool


class _FakeClock:
    """A hand-cranked monotonic clock for deterministic deadline tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class TestConstruction:
    def test_rejects_non_budget(self) -> None:
        with pytest.raises(TypeError, match="RunBudget"):
            RunBudgetMeter(object())  # type: ignore[arg-type]

    def test_creates_own_token_when_absent(self) -> None:
        meter = RunBudgetMeter(RunBudget())
        assert isinstance(meter.token, CancellationToken)
        assert meter.token.cancelled is False


class TestIterationBreach:
    def test_breach_raises_and_cancels_shared_token(self) -> None:
        token = CancellationToken()
        meter = RunBudgetMeter(RunBudget(max_iterations=2), token=token)
        meter.spend_iteration()
        meter.spend_iteration()  # exactly at cap: ok
        assert meter.iterations == 2
        with pytest.raises(BudgetBreachError) as excinfo:
            meter.spend_iteration()
        assert excinfo.value.limit is BudgetLimit.ITERATIONS
        # Shared token flipped so sibling tasks can unwind.
        assert token.cancelled is True
        assert "iterations" in (token.reason or "")
        # Counter reflects the spend; no partial rollback surprises.
        assert meter.iterations == 3


class TestTokenBreach:
    def test_token_budget_breach(self) -> None:
        meter = RunBudgetMeter(RunBudget(max_tokens=50))
        meter.spend_tokens(50)
        assert meter.tokens == 50
        with pytest.raises(BudgetBreachError) as excinfo:
            meter.spend_tokens(1)
        assert excinfo.value.limit is BudgetLimit.TOKENS
        assert meter.token.cancelled is True


class TestDeadlineBreach:
    def test_deadline_breach_uses_injected_clock(self) -> None:
        clock = _FakeClock()
        meter = RunBudgetMeter(RunBudget(deadline_seconds=1.0), monotonic=clock)
        clock.now = 0.9
        meter.checkpoint()  # under deadline: ok
        clock.now = 1.5
        with pytest.raises(BudgetBreachError) as excinfo:
            meter.checkpoint()
        assert excinfo.value.limit is BudgetLimit.DEADLINE
        assert meter.token.cancelled is True


class _SlowTool(Tool):
    """Tool that waits on the meter's cancellation token, modelling a loop leg."""

    def __init__(self, *, name: str, token: CancellationToken) -> None:
        self._name = name
        self._token = token
        self.completed = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "waits then checks cancellation"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        # Cooperative: if the run was cancelled, unwind cleanly rather than
        # completing and mutating state.
        self._token.raise_if_cancelled()
        self.completed = True
        return self._name


class TestCleanCancellation:
    async def test_breach_cancels_in_flight_leg_without_completion(self) -> None:
        token = CancellationToken()
        meter = RunBudgetMeter(RunBudget(max_iterations=1), token=token)
        tool = _SlowTool(name="leg", token=token)

        # First iteration is allowed.
        meter.spend_iteration()
        # Second iteration breaches, cancelling the shared token.
        with pytest.raises(BudgetBreachError):
            meter.spend_iteration()

        # A leg run after the breach observes cancellation cooperatively: it
        # unwinds via CancelledError without completing (no partial state), so
        # its side-effecting body never runs.
        with pytest.raises(asyncio.CancelledError):
            await tool.invoke({})
        assert tool.completed is False

    async def test_shared_token_wakes_waiting_sibling(self) -> None:
        token = CancellationToken()
        meter = RunBudgetMeter(RunBudget(max_tokens=1), token=token)

        async def sibling() -> str:
            await token.wait()
            return "unblocked"

        task = asyncio.ensure_future(sibling())
        await asyncio.sleep(0)  # let sibling block on the token
        with pytest.raises(BudgetBreachError):
            meter.spend_tokens(2)
        assert await task == "unblocked"
