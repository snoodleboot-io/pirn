"""Unit tests for :class:`TaskPlanner`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.plan_and_execute.task_planner import (
    TaskPlanner,
)
from pirn.domains.agents.types.plan import Plan
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestTaskPlannerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_parses_numbered_steps_from_llm_response(self) -> None:
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

    async def test_stores_raw_response_as_rationale(self) -> None:
        raw = "1. Step one\n2. Step two"
        llm = StubLLMProvider([raw])
        with Tapestry() as t:
            TaskPlanner(
                goal="Do something.",
                llm=llm,
                _config=KnotConfig(id="planner"),
            )
        result = await t.run(RunRequest())
        plan = result.outputs["planner"]
        assert plan.rationale == raw

    async def test_handles_paren_numbered_list(self) -> None:
        llm = StubLLMProvider(["1) First\n2) Second"])
        with Tapestry() as t:
            TaskPlanner(
                goal="goal",
                llm=llm,
                _config=KnotConfig(id="planner"),
            )
        result = await t.run(RunRequest())
        plan = result.outputs["planner"]
        assert plan.steps == ("First", "Second")

    async def test_empty_response_yields_empty_steps(self) -> None:
        llm = StubLLMProvider(["No numbered steps here."])
        with Tapestry() as t:
            TaskPlanner(
                goal="goal",
                llm=llm,
                _config=KnotConfig(id="planner"),
            )
        result = await t.run(RunRequest())
        plan = result.outputs["planner"]
        assert plan.steps == ()


class TestTaskPlannerConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                TaskPlanner(
                    goal="goal",
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="planner"),
                )
