"""Tests for :class:`ReWooPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rewoo.rewoo_pipeline import ReWooPipeline
from pirn_agents.specializations.rewoo.rewoo_result import ReWooResult
from pirn_agents.types.tool_status import ToolStatus
from tests.specializations.conftest import StubLLMProvider, StubTool


class TestReWooPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_plan_execute_synthesize_end_to_end(self) -> None:
        llm = StubLLMProvider(["1. search: foo\n2. calc: 2+2", "final answer"])
        tools = (
            StubTool(name="search", handler="hit"),
            StubTool(name="calc", handler=4),
        )
        with Tapestry() as t:
            ReWooPipeline(
                goal="solve it",
                llm=llm,
                tools=tools,
                _config=KnotConfig(id="rewoo"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["rewoo"]
        assert isinstance(result, ReWooResult)
        assert result.answer == "final answer"
        assert len(result.plan) == 2
        assert len(result.results) == 2
        assert all(r.status is ToolStatus.OK for r in result.results)

    async def test_only_two_llm_round_trips(self) -> None:
        llm = StubLLMProvider(["1. search: a\n2. search: b\n3. search: c", "answer"])
        tools = (StubTool(name="search", handler="ok"),)
        with Tapestry() as t:
            ReWooPipeline(
                goal="g",
                llm=llm,
                tools=tools,
                _config=KnotConfig(id="rewoo"),
            )
        await t.run(RunRequest())
        # One plan call + one synthesis call, regardless of the 3 planned tools.
        assert len(llm.calls) == 2

    async def test_tools_actually_invoked(self) -> None:
        llm = StubLLMProvider(["1. search: foo", "answer"])
        tool = StubTool(name="search", handler="hit")
        with Tapestry() as t:
            ReWooPipeline(
                goal="g",
                llm=llm,
                tools=(tool,),
                _config=KnotConfig(id="rewoo"),
            )
        await t.run(RunRequest())
        assert tool.invocations == [{"input": "foo"}]

    async def test_rejects_bad_max_concurrency(self) -> None:
        llm = StubLLMProvider(["x", "y"])
        with Tapestry():
            knot = ReWooPipeline.__new__(ReWooPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="rewoo"))
        with self.assertRaises(ValueError):
            await knot.process(goal="g", llm=llm, tools=(), max_concurrency=0)

    async def test_rejects_non_llm_provider(self) -> None:
        with Tapestry():
            knot = ReWooPipeline.__new__(ReWooPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="rewoo"))
        with self.assertRaises(TypeError):
            await knot.process(goal="g", llm="bad", tools=())  # type: ignore[arg-type]
