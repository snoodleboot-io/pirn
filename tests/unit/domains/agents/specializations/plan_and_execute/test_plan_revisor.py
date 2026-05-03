"""Unit tests for :class:`PlanRevisor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.plan_and_execute.plan_revisor import (
    PlanRevisor,
)
from pirn.domains.agents.types.plan import Plan
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


@knot
async def original_plan() -> Plan:
    return Plan(steps=("step A", "step B", "step C"))


@pytest.mark.asyncio
class TestPlanRevisorProcess:
    async def test_returns_revised_plan_with_parsed_steps(self) -> None:
        llm = StubLLMProvider(["1. revised-step-one\n2. revised-step-two"])
        with Tapestry() as t:
            p = original_plan(_config=KnotConfig(id="p"))
            PlanRevisor(
                original_plan=p,
                completed_results="Step A done.",
                failure_reason="Step B timed out.",
                llm=llm,
                _config=KnotConfig(id="revisor"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        plan = result.outputs["revisor"]
        assert isinstance(plan, Plan)
        assert plan.steps == ("revised-step-one", "revised-step-two")

    async def test_context_includes_original_steps_and_failure(self) -> None:
        llm = StubLLMProvider(["1. fallback step"])
        with Tapestry() as t:
            p = original_plan(_config=KnotConfig(id="p"))
            PlanRevisor(
                original_plan=p,
                completed_results="partial results",
                failure_reason="network error",
                llm=llm,
                _config=KnotConfig(id="revisor"),
            )
        await t.run(RunRequest())
        messages = llm.calls[0]
        user_content = messages[-1]["content"]
        assert "step A" in user_content
        assert "partial results" in user_content
        assert "network error" in user_content


@pytest.mark.asyncio
class TestPlanRevisorConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="LLMProvider"):
            with Tapestry():
                p = original_plan(_config=KnotConfig(id="p"))
                PlanRevisor(
                    original_plan=p,
                    completed_results="done",
                    failure_reason="failed",
                    llm=42,  # type: ignore[arg-type]
                    _config=KnotConfig(id="revisor"),
                )
