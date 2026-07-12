"""Tests for :class:`ReWooPlanner`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rewoo.rewoo_planner import ReWooPlanner
from pirn_agents.types.tool_call import ToolCall
from tests.specializations.conftest import StubLLMProvider


class TestReWooPlannerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_parses_numbered_plan_into_tool_calls(self) -> None:
        llm = StubLLMProvider(["1. search: quantum\n2. calc: 2+2\n"])
        with Tapestry() as t:
            ReWooPlanner(
                goal="answer it",
                llm=llm,
                tool_descriptions="- search: web\n- calc: math",
                _config=KnotConfig(id="plan"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        calls = result.outputs["plan"]
        assert isinstance(calls, tuple)
        assert [c.tool_name for c in calls] == ["search", "calc"]
        assert calls[0] == ToolCall(
            tool_name="search", arguments={"input": "quantum"}, call_id="c0"
        )
        assert calls[1].arguments == {"input": "2+2"}

    async def test_single_llm_round_trip(self) -> None:
        llm = StubLLMProvider(["1. search: x"])
        with Tapestry() as t:
            ReWooPlanner(
                goal="g",
                llm=llm,
                tool_descriptions="- search: web",
                _config=KnotConfig(id="plan"),
            )
        await t.run(RunRequest())
        assert len(llm.calls) == 1

    async def test_ignores_non_plan_lines(self) -> None:
        llm = StubLLMProvider(["Here is the plan:\n1. search: x\nThanks!"])
        with Tapestry() as t:
            ReWooPlanner(
                goal="g",
                llm=llm,
                tool_descriptions="- search: web",
                _config=KnotConfig(id="plan"),
            )
        result = await t.run(RunRequest())
        calls = result.outputs["plan"]
        assert len(calls) == 1
        assert calls[0].tool_name == "search"

    async def test_rejects_non_llm_provider(self) -> None:
        with Tapestry():
            knot = ReWooPlanner.__new__(ReWooPlanner)
            object.__setattr__(knot, "_config", KnotConfig(id="plan"))
        with self.assertRaises(TypeError):
            await knot.process(goal="g", llm="bad", tool_descriptions="")  # type: ignore[arg-type]

    async def test_rejects_non_string_goal(self) -> None:
        llm = StubLLMProvider(["1. search: x"])
        with Tapestry():
            knot = ReWooPlanner.__new__(ReWooPlanner)
            object.__setattr__(knot, "_config", KnotConfig(id="plan"))
        with self.assertRaises(TypeError):
            await knot.process(goal=1, llm=llm, tool_descriptions="")  # type: ignore[arg-type]
