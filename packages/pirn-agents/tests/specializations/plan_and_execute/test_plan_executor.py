"""Unit tests for :class:`PlanExecutor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.plan_and_execute.plan_executor import (
    PlanExecutor,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.types.plan import Plan
from pirn.tapestry import Tapestry

from tests.specializations.conftest import StubLLMProvider


@knot
async def emit_plan() -> Plan:
    return Plan(steps=("step one", "step two", "step three"))


def _make_knot(llm: StubLLMProvider) -> PlanExecutor:
    with Tapestry():
        return PlanExecutor(plan=Plan(steps=()), llm=llm, _config=KnotConfig(id="exec"))


class TestPlanExecutorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_executes_each_step_and_returns_combined_response(self) -> None:
        llm = StubLLMProvider(["result-one", "result-two", "result-three"])
        k = _make_knot(llm)
        plan = Plan(steps=("step one", "step two", "step three"))
        response = await k.process(plan=plan, llm=llm)
        assert isinstance(response, AgentResponse)
        assert "result-one" in response.content
        assert "result-two" in response.content
        assert "result-three" in response.content

    async def test_makes_one_call_per_step(self) -> None:
        llm = StubLLMProvider(["r1", "r2"])
        k = _make_knot(llm)
        plan = Plan(steps=("a", "b"))
        await k.process(plan=plan, llm=llm)
        assert len(llm.calls) == 2

    async def test_empty_plan_returns_empty_content(self) -> None:
        llm = StubLLMProvider([])
        k = _make_knot(llm)
        plan = Plan(steps=())
        response = await k.process(plan=plan, llm=llm)
        assert isinstance(response, AgentResponse)
        assert response.content == ""

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["r"])
        k = _make_knot(llm)
        plan = Plan(steps=("a",))
        with self.assertRaises(TypeError):
            await k.process(plan=plan, llm="bad")  # type: ignore[arg-type]

    async def test_rejects_non_plan(self) -> None:
        llm = StubLLMProvider(["r"])
        k = _make_knot(llm)
        with self.assertRaises(TypeError):
            await k.process(plan="not-a-plan", llm=llm)  # type: ignore[arg-type]

    async def test_tapestry_run_integration(self) -> None:
        llm = StubLLMProvider(["result-one", "result-two", "result-three"])
        with Tapestry() as t:
            p = emit_plan(_config=KnotConfig(id="p"))
            PlanExecutor(plan=p, llm=llm, _config=KnotConfig(id="exec"))
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["exec"]
        assert isinstance(response, AgentResponse)
        assert "result-one" in response.content
