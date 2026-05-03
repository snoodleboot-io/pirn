"""Unit tests for :class:`PlanExecutor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.plan_and_execute.plan_executor import (
    PlanExecutor,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.agents.types.plan import Plan
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


@knot
async def emit_plan() -> Plan:
    return Plan(steps=("step one", "step two", "step three"))


@pytest.mark.asyncio
class TestPlanExecutorProcess:
    async def test_executes_each_step_and_returns_combined_response(self) -> None:
        llm = StubLLMProvider(["result-one", "result-two", "result-three"])
        with Tapestry() as t:
            p = emit_plan(_config=KnotConfig(id="p"))
            PlanExecutor(plan=p, llm=llm, _config=KnotConfig(id="exec"))
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["exec"]
        assert isinstance(response, AgentResponse)
        assert "result-one" in response.content
        assert "result-two" in response.content
        assert "result-three" in response.content

    async def test_makes_one_call_per_step(self) -> None:
        llm = StubLLMProvider(["r1", "r2"])
        with Tapestry() as t:

            @knot
            async def two_step_plan() -> Plan:
                return Plan(steps=("a", "b"))

            p = two_step_plan(_config=KnotConfig(id="p"))
            PlanExecutor(plan=p, llm=llm, _config=KnotConfig(id="exec"))
        await t.run(RunRequest())
        assert len(llm.calls) == 2

    async def test_empty_plan_returns_empty_content(self) -> None:
        llm = StubLLMProvider([])

        with Tapestry() as t:

            @knot
            async def empty_plan() -> Plan:
                return Plan(steps=())

            p = empty_plan(_config=KnotConfig(id="p"))
            PlanExecutor(plan=p, llm=llm, _config=KnotConfig(id="exec"))
        result = await t.run(RunRequest())
        response = result.outputs["exec"]
        assert isinstance(response, AgentResponse)
        assert response.content == ""


@pytest.mark.asyncio
class TestPlanExecutorConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="LLMProvider"):
            with Tapestry() as t:
                p = emit_plan(_config=KnotConfig(id="p"))
                PlanExecutor(
                    plan=p,
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="exec"),
                )
