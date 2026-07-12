"""Tests for :class:`PlanReActPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.plan_react.plan_react_pipeline import PlanReActPipeline
from pirn_agents.specializations.plan_react.plan_react_result import PlanReActResult
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


class TestPlanReActPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_plans_then_reacts_each_step(self) -> None:
        # 1 planner call, then one ReAct (max_iterations=1) call per step.
        llm = StubLLMProvider(
            ["1. gather facts\n2. summarise", "Final Answer: facts", "Final Answer: summary"]
        )
        with Tapestry() as t:
            PlanReActPipeline(
                task="write a report",
                llm=llm,
                max_iterations=1,
                _config=KnotConfig(id="pr"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["pr"]
        assert isinstance(result, PlanReActResult)
        assert result.plan == ("gather facts", "summarise")
        assert len(result.step_responses) == 2
        assert isinstance(result.final, AgentResponse)
        assert "summary" in result.final.content

    async def test_falls_back_to_task_when_plan_empty(self) -> None:
        llm = StubLLMProvider(["no numbered steps here", "Final Answer: done"])
        with Tapestry() as t:
            PlanReActPipeline(
                task="just do it", llm=llm, max_iterations=1, _config=KnotConfig(id="pr")
            )
        run = await t.run(RunRequest())
        result = run.outputs["pr"]
        assert result.plan == ("just do it",)
        assert len(result.step_responses) == 1

    async def test_bounds_steps(self) -> None:
        llm = StubLLMProvider(
            ["1. a\n2. b\n3. c", "Final Answer: ra", "Final Answer: rb", "Final Answer: rc"]
        )
        with Tapestry() as t:
            PlanReActPipeline(
                task="q", llm=llm, max_iterations=1, max_steps=2, _config=KnotConfig(id="pr")
            )
        run = await t.run(RunRequest())
        result = run.outputs["pr"]
        assert result.plan == ("a", "b")
        assert len(result.step_responses) == 2

    async def test_rejects_non_positive_iterations(self) -> None:
        llm = StubLLMProvider(["1. a"])
        with Tapestry():
            knot = PlanReActPipeline.__new__(PlanReActPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="pr"))
        with self.assertRaises(ValueError):
            await knot.process(task="q", llm=llm, max_iterations=0)
