"""Tests for :class:`AgenticRagPipeline`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.agentic_rag_pipeline import AgenticRagPipeline
from pirn_agents.tool import Tool
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider, StubTool


def _answer_tool() -> StubTool:
    def _handler(args: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"answer": f"answer for {args['question']}", "sources": []}

    return StubTool(name="rag", handler=_handler)


class TestAgenticRagPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_loops_until_done(self) -> None:
        tool = _answer_tool()
        # First round -> follow up; second round -> done.
        llm = StubLLMProvider(["FOLLOWUP: sharper question", "DONE"])
        with Tapestry() as t:
            AgenticRagPipeline(
                query="original question",
                rag_tool=tool,
                llm=llm,
                max_iterations=3,
                _config=KnotConfig(id="agentic"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["agentic"]
        assert isinstance(response, AgentResponse)
        assert response.content == "answer for sharper question"
        assert [inv["question"] for inv in tool.invocations] == [
            "original question",
            "sharper question",
        ]

    async def test_stops_immediately_when_done(self) -> None:
        tool = _answer_tool()
        llm = StubLLMProvider(["DONE"])
        with Tapestry() as t:
            AgenticRagPipeline(
                query="q",
                rag_tool=tool,
                llm=llm,
                max_iterations=3,
                _config=KnotConfig(id="agentic"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert len(tool.invocations) == 1

    async def test_bounded_by_max_iterations(self) -> None:
        tool = _answer_tool()
        # LLM always wants more, but budget caps the calls at 2.
        llm = StubLLMProvider(["FOLLOWUP: more"])
        with Tapestry() as t:
            AgenticRagPipeline(
                query="q",
                rag_tool=tool,
                llm=llm,
                max_iterations=2,
                _config=KnotConfig(id="agentic"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert len(tool.invocations) == 2

    async def test_rag_tool_is_a_tool(self) -> None:
        assert isinstance(_answer_tool(), Tool)

    async def test_rejects_non_tool(self) -> None:
        with Tapestry():
            knot = AgenticRagPipeline.__new__(AgenticRagPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(TypeError, "rag_tool must be a Tool"):
            await knot.process(query="q", rag_tool="nope", llm=StubLLMProvider(["DONE"]))  # type: ignore[arg-type]
