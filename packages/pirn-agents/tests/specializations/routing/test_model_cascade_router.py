"""Mirrored tests for :class:`ModelCascadeRouter` cheap-first escalation (PIR-508).

Tiers wrap stub LLM providers (no vendor SDK) and confidence is an injected
stub, so escalation, observability, and spend-cap interaction are deterministic.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

import pytest
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.performance.spend_cap_policy import SpendCapPolicy
from pirn_agents.specializations.routing.cascade_tier import CascadeTier
from pirn_agents.specializations.routing.model_cascade_router import ModelCascadeRouter
from tests.conftest import StubLLMProvider


async def _run(tapestry: Tapestry, knot_id: str = "cascade"):
    result = await tapestry.run(RunRequest())
    assert result.succeeded
    return result.outputs[knot_id]


class _DownProvider(LLMProvider):
    """A provider whose every call fails."""

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        raise RuntimeError("tier down")


def _tier(name: str, output: str, *, min_confidence: float = 0.0, cost: float = 0.0) -> CascadeTier:
    return CascadeTier(
        name=name,
        llm=StubLLMProvider([output]),
        min_confidence=min_confidence,
        estimated_cost=cost,
    )


def _prompts_sent(tier: CascadeTier) -> list[str]:
    """The user prompt of every call the tier's stub provider received."""
    assert isinstance(tier.llm, StubLLMProvider)
    return [str(call[-1]["content"]) for call in tier.llm.calls]


def _failing_tier(name: str, *, cost: float = 0.0) -> CascadeTier:
    return CascadeTier(name=name, llm=_DownProvider(), estimated_cost=cost)


def _confidence_from(table: dict[str, float]) -> Callable[[object], Awaitable[float]]:
    async def score(value: object) -> float:
        return table.get(str(value), 0.0)

    return score


class TestValidation:
    async def test_empty_tiers_rejected(self) -> None:
        with Tapestry():
            router = ModelCascadeRouter(
                request="q",
                tiers=[],
                confidence=_confidence_from({}),
                _config=KnotConfig(id="cascade"),
            )
        with pytest.raises(ValueError, match="non-empty"):
            await router.process(request="q", tiers=[], confidence=_confidence_from({}))

    def test_non_tier_rejected(self) -> None:
        with pytest.raises(TypeError, match="CascadeTier"):
            ModelCascadeRouter(
                request="q",
                tiers=["nope"],
                confidence=_confidence_from({}),
                _config=KnotConfig(id="cascade"),
            )  # type: ignore[list-item]

    def test_bad_min_confidence_rejected(self) -> None:
        with pytest.raises(ValueError, match="min_confidence"):
            _tier("t", "x", min_confidence=2.0)

    def test_non_provider_rejected(self) -> None:
        with pytest.raises(TypeError, match="LLMProvider"):
            CascadeTier(name="t", llm="not-a-provider")  # type: ignore[arg-type]


class TestCheapFirst:
    async def test_cheap_tier_accepted_without_escalation(self) -> None:
        tiers = [_tier("cheap", "A", min_confidence=0.5), _tier("strong", "B")]
        with Tapestry() as t:
            ModelCascadeRouter(
                request="q",
                tiers=tiers,
                confidence=_confidence_from({"A": 0.9}),
                _config=KnotConfig(id="cascade"),
            )
        outcome = await _run(t)

        assert outcome.value == "A"
        assert outcome.chosen == "cheap"
        assert outcome.escalated is False
        assert outcome.attempted == ("cheap",)  # strong never invoked
        assert _prompts_sent(tiers[1]) == []

    async def test_each_attempted_tier_is_an_llm_call_knot_with_its_own_lineage(self) -> None:
        history = InMemoryHistory()
        tiers = [_tier("cheap", "A", min_confidence=0.8), _tier("strong", "B")]
        with Tapestry(history=history) as t:
            ModelCascadeRouter(
                request="q",
                tiers=tiers,
                confidence=_confidence_from({"A": 0.1, "B": 1.0}),
                _config=KnotConfig(id="cascade"),
            )
        await _run(t)

        # The provider saw the prompt as a user message, once per attempted tier.
        assert _prompts_sent(tiers[0]) == ["q"]
        assert _prompts_sent(tiers[1]) == ["q"]
        assert len(await history.query_lineage_by_knot_id("invoke")) == 2

    async def test_low_confidence_escalates(self) -> None:
        tiers = [_tier("cheap", "A", min_confidence=0.8), _tier("strong", "B", min_confidence=0.8)]
        with Tapestry() as t:
            ModelCascadeRouter(
                request="q",
                tiers=tiers,
                confidence=_confidence_from({"A": 0.3, "B": 0.95}),
                _config=KnotConfig(id="cascade"),
            )
        outcome = await _run(t)

        assert outcome.value == "B"
        assert outcome.chosen == "strong"
        assert outcome.escalated is True
        assert outcome.attempted == ("cheap", "strong")

    async def test_failure_escalates(self) -> None:
        tiers = [_failing_tier("cheap"), _tier("strong", "B", min_confidence=0.5)]
        with Tapestry() as t:
            ModelCascadeRouter(
                request="q",
                tiers=tiers,
                confidence=_confidence_from({"B": 0.9}),
                _config=KnotConfig(id="cascade"),
            )
        outcome = await _run(t)

        assert outcome.chosen == "strong"
        assert any("failed" in d for d in outcome.decisions)

    async def test_all_low_confidence_returns_best_effort(self) -> None:
        tiers = [_tier("cheap", "A", min_confidence=0.9), _tier("strong", "B", min_confidence=0.9)]
        with Tapestry() as t:
            ModelCascadeRouter(
                request="q",
                tiers=tiers,
                confidence=_confidence_from({"A": 0.1, "B": 0.2}),
                _config=KnotConfig(id="cascade"),
            )
        outcome = await _run(t)

        assert outcome.succeeded is False
        assert outcome.chosen == "strong"  # last tier's best-effort output
        assert outcome.value == "B"


class TestObservability:
    async def test_decisions_are_logged(self) -> None:
        tiers = [_tier("cheap", "A", min_confidence=0.8), _tier("strong", "B")]
        with Tapestry() as t:
            ModelCascadeRouter(
                request="q",
                tiers=tiers,
                confidence=_confidence_from({"A": 0.2, "B": 1.0}),
                _config=KnotConfig(id="cascade"),
            )
        outcome = await _run(t)

        assert "cheap: low confidence=0.2 -> escalate" in outcome.decisions
        assert "strong: accepted (confidence=1.0)" in outcome.decisions


class TestSpendCapInteraction:
    async def test_downshift_declines_to_escalate(self) -> None:
        meter = RunBudgetMeter(RunBudget(max_cost=1.0))
        tiers = [
            _tier("cheap", "A", min_confidence=0.9, cost=0.5),
            _tier("strong", "B", min_confidence=0.9, cost=1.0),
        ]
        with Tapestry() as t:
            ModelCascadeRouter(
                request="q",
                tiers=tiers,
                confidence=_confidence_from({"A": 0.1}),
                meter=meter,
                spend_cap_policy=SpendCapPolicy.DOWNSHIFT,
                _config=KnotConfig(id="cascade"),
            )
        outcome = await _run(t)

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
        history = InMemoryHistory()
        with Tapestry(history=history) as t:
            ModelCascadeRouter(
                request="q",
                tiers=tiers,
                confidence=_confidence_from({"A": 0.1}),
                meter=meter,
                spend_cap_policy=SpendCapPolicy.ABORT,
                _config=KnotConfig(id="cascade"),
            )

        # BudgetBreachError is now raised inside a nested AttemptTier knot,
        # so the engine records the failure rather than propagating the
        # original exception out of t.run() -- each level wraps it as a
        # SubTapestryError whose message names the next run to look in. Three
        # levels deep (ADR agents-speaks-core WS5b): ModelCascadeRouter's own
        # inner run contains the CascadeLoop knot (itself a SubTapestry);
        # CascadeLoop's own inner run contains the failing iteration's
        # IterationChainKnot (whose SubTapestryError message names the
        # iteration's own run); that run is where AttemptTier's raw
        # BudgetBreachError actually lives.
        run = await t.run(RunRequest())
        assert not run.succeeded
        cascade_row = next(row for row in run.lineage if row.knot_id == "cascade")
        cascade_inner_run = await history.get_run(cascade_row.extra["inner_run_id"])
        loop_row = next(row for row in cascade_inner_run.lineage if row.knot_id == "cascade_loop")
        loop_inner_run = await history.get_run(loop_row.extra["inner_run_id"])
        iteration_exc = next(
            exc for exc in loop_inner_run.exceptions if exc.exc_type == "SubTapestryError"
        )
        iteration_run_id = re.search(r"run_id='([^']+)'", iteration_exc.message).group(1)
        iteration_run = await history.get_run(iteration_run_id)
        assert any(exc.exc_type == BudgetBreachError.__name__ for exc in iteration_run.exceptions)

    async def test_under_cap_accrues_cost(self) -> None:
        meter = RunBudgetMeter(RunBudget(max_cost=10.0))
        tiers = [_tier("cheap", "A", min_confidence=0.0, cost=2.0)]
        with Tapestry() as t:
            ModelCascadeRouter(
                request="q",
                tiers=tiers,
                confidence=_confidence_from({"A": 1.0}),
                meter=meter,
                _config=KnotConfig(id="cascade"),
            )
        outcome = await _run(t)

        assert outcome.succeeded is True
        assert meter.cost == pytest.approx(2.0)
