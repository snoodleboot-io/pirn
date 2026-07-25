"""Unit tests for :class:`TaskPlanner`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.plan_and_execute.task_planner import (
    TaskPlanner,
)
from pirn_agents.types.plan import Plan
from tests.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider, goal: str = "goal") -> TaskPlanner:
    with Tapestry():
        return TaskPlanner(goal=goal, llm=llm, _config=KnotConfig(id="planner"))


class TestTaskPlannerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_parses_numbered_steps_from_llm_response(self) -> None:
        llm = StubLLMProvider(["1. Research the topic\n2. Write outline\n3. Draft article"])
        k = _make_knot(llm)
        plan = await k.process(goal="Write an article about AI.", llm=llm)
        assert isinstance(plan, Plan)
        assert plan.steps == ("Research the topic", "Write outline", "Draft article")

    async def test_stores_raw_response_as_rationale(self) -> None:
        raw = "1. Step one\n2. Step two"
        llm = StubLLMProvider([raw])
        k = _make_knot(llm)
        plan = await k.process(goal="Do something.", llm=llm)
        assert plan.rationale == raw

    async def test_handles_paren_numbered_list(self) -> None:
        llm = StubLLMProvider(["1) First\n2) Second"])
        k = _make_knot(llm)
        plan = await k.process(goal="goal", llm=llm)
        assert plan.steps == ("First", "Second")

    async def test_empty_response_yields_empty_steps(self) -> None:
        llm = StubLLMProvider(["No numbered steps here."])
        k = _make_knot(llm)
        plan = await k.process(goal="goal", llm=llm)
        assert plan.steps == ()

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["1. step"])
        k = _make_knot(llm)
        with self.assertRaises(TypeError):
            await k.process(goal="goal", llm="bad")  # type: ignore[arg-type]

    async def test_rejects_non_string_goal(self) -> None:
        llm = StubLLMProvider(["1. step"])
        k = _make_knot(llm)
        with self.assertRaises(TypeError):
            await k.process(goal=42, llm=llm)  # type: ignore[arg-type]

    async def test_tapestry_run_integration(self) -> None:
        llm = StubLLMProvider(["1. Research the topic\n2. Write outline\n3. Draft article"])
        with Tapestry() as t:
            TaskPlanner(
                goal="Write an article about AI.",
                llm=llm,
                _config=KnotConfig(id="planner"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        plan = result.outputs["planner"]
        assert isinstance(plan, Plan)
        assert plan.steps == ("Research the topic", "Write outline", "Draft article")
