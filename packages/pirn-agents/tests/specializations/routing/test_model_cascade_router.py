"""Mirrored tests for :class:`ModelCascadeRouter` cheap-first escalation (PIR-508).

Tiers wrap stub provider callables (no vendor SDK) and confidence is an injected
stub, so escalation, observability, and spend-cap interaction are deterministic.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest

from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.performance.spend_cap_policy import SpendCapPolicy
from pirn_agents.specializations.routing.cascade_tier import CascadeTier
from pirn_agents.specializations.routing.model_cascade_router import ModelCascadeRouter


def _tier(name: str, output: str, *, min_confidence: float = 0.0, cost: float = 0.0) -> CascadeTier:
    async def invoke(_request: object) -> str:
        return output

    return CascadeTier(name=name, invoke=invoke, min_confidence=min_confidence, estimated_cost=cost)


def _failing_tier(name: str, *, cost: float = 0.0) -> CascadeTier:
    async def invoke(_request: object) -> str:
        raise RuntimeError("tier down")

    return CascadeTier(name=name, invoke=invoke, estimated_cost=cost)


def _confidence_from(table: dict[str, float]) -> Callable[[object], Awaitable[float]]:
    async def score(value: object) -> float:
        return table.get(str(value), 0.0)

    return score


class TestValidation:
    def test_empty_tiers_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            ModelCascadeRouter([], _confidence_from({}))

    def test_non_tier_rejected(self) -> None:
        with pytest.raises(TypeError, match="CascadeTier"):
            ModelCascadeRouter(["nope"], _confidence_from({}))  # type: ignore[list-item]

    def test_bad_min_confidence_rejected(self) -> None:
        with pytest.raises(ValueError, match="min_confidence"):
            _tier("t", "x", min_confidence=2.0)


class TestCheapFirst:
    async def test_cheap_tier_accepted_without_escalation(self) -> None:
        tiers = [_tier("cheap", "A", min_confidence=0.5), _tier("strong", "B")]
        router = ModelCascadeRouter(tiers, _confidence_from({"A": 0.9}))

        outcome = await router.route("q")

        assert outcome.value == "A"
        assert outcome.chosen == "cheap"
        assert outcome.escalated is False
        assert outcome.attempted == ("cheap",)  # strong never invoked

    async def test_low_confidence_escalates(self) -> None:
        tiers = [_tier("cheap", "A", min_confidence=0.8), _tier("strong", "B", min_confidence=0.8)]
        router = ModelCascadeRouter(tiers, _confidence_from({"A": 0.3, "B": 0.95}))

        outcome = await router.route("q")

        assert outcome.value == "B"
        assert outcome.chosen == "strong"
        assert outcome.escalated is True
        assert outcome.attempted == ("cheap", "strong")

    async def test_failure_escalates(self) -> None:
        tiers = [_failing_tier("cheap"), _tier("strong", "B", min_confidence=0.5)]
        router = ModelCascadeRouter(tiers, _confidence_from({"B": 0.9}))

        outcome = await router.route("q")

        assert outcome.chosen == "strong"
        assert any("failed" in d for d in outcome.decisions)

    async def test_all_low_confidence_returns_best_effort(self) -> None:
        tiers = [_tier("cheap", "A", min_confidence=0.9), _tier("strong", "B", min_confidence=0.9)]
        router = ModelCascadeRouter(tiers, _confidence_from({"A": 0.1, "B": 0.2}))

        outcome = await router.route("q")

        assert outcome.succeeded is False
        assert outcome.chosen == "strong"  # last tier's best-effort output
        assert outcome.value == "B"


class TestObservability:
    async def test_decisions_are_logged(self) -> None:
        tiers = [_tier("cheap", "A", min_confidence=0.8), _tier("strong", "B")]
        router = ModelCascadeRouter(tiers, _confidence_from({"A": 0.2, "B": 1.0}))

        outcome = await router.route("q")

        assert "cheap: low confidence=0.2 -> escalate" in outcome.decisions
        assert "strong: accepted (confidence=1.0)" in outcome.decisions


class TestSpendCapInteraction:
    async def test_downshift_declines_to_escalate(self) -> None:
        meter = RunBudgetMeter(RunBudget(max_cost=1.0))
        tiers = [
            _tier("cheap", "A", min_confidence=0.9, cost=0.5),
            _tier("strong", "B", min_confidence=0.9, cost=1.0),
        ]
        router = ModelCascadeRouter(
            tiers,
            _confidence_from({"A": 0.1}),
            meter=meter,
            spend_cap_policy=SpendCapPolicy.DOWNSHIFT,
        )

        outcome = await router.route("q")

        # cheap spent 0.5; escalating to strong (1.0 more) would breach the 1.0 cap
        assert outcome.chosen == "cheap"
        assert any("downshift" in d for d in outcome.decisions)
        assert meter.cost == pytest.approx(0.5)

    async def test_abort_raises_budget_breach(self) -> None:
        meter = RunBudgetMeter(RunBudget(max_cost=1.0))
        tiers = [
            _tier("cheap", "A", min_confidence=0.9, cost=0.5),
            _tier("strong", "B", min_confidence=0.9, cost=1.0),
        ]
        router = ModelCascadeRouter(
            tiers, _confidence_from({"A": 0.1}), meter=meter, spend_cap_policy=SpendCapPolicy.ABORT
        )

        with pytest.raises(BudgetBreachError):
            await router.route("q")

    async def test_under_cap_accrues_cost(self) -> None:
        meter = RunBudgetMeter(RunBudget(max_cost=10.0))
        tiers = [_tier("cheap", "A", min_confidence=0.0, cost=2.0)]
        router = ModelCascadeRouter(tiers, _confidence_from({"A": 1.0}), meter=meter)

        outcome = await router.route("q")

        assert outcome.succeeded is True
        assert meter.cost == pytest.approx(2.0)
