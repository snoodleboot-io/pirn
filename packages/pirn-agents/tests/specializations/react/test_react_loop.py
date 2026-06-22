"""Tests for :class:`ReActLoop`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.agent_message import AgentMessage
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry

from tests.specializations.conftest import (
    StubLLMProvider,
    StubTool,
)


class TestReActLoopProcess(unittest.IsolatedAsyncioTestCase):
    def _make(
        self,
        llm: StubLLMProvider,
        tools: tuple = (),
        max_iterations: int = 4,
    ) -> ReActLoop:
        with Tapestry():
            return ReActLoop(
                messages=(AgentMessage(role="user", content="hi"),),
                llm=llm,
                tools=tools,
                max_iterations=max_iterations,
                _config=KnotConfig(id="loop"),
            )

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["Final Answer: ok"])
        knot = self._make(llm)
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await knot.process(
                messages=(AgentMessage(role="user", content="hi"),),
                llm="not-a-provider",  # type: ignore[arg-type]
                tools=(),
                max_iterations=1,
            )

    async def test_rejects_zero_max_iterations(self) -> None:
        llm = StubLLMProvider(["Final Answer: ok"])
        knot = self._make(llm)
        with self.assertRaisesRegex(ValueError, "max_iterations"):
            await knot.process(
                messages=(AgentMessage(role="user", content="hi"),),
                llm=llm,
                tools=(),
                max_iterations=0,
            )

    async def test_returns_agent_response_on_final_answer(self) -> None:
        llm = StubLLMProvider(
            [
                "Action: search\nAction Input: foo",
                "Final Answer: 42 is the answer",
            ]
        )
        tool = StubTool(name="search", handler="found foo")
        with Tapestry() as t:
            ReActLoop(
                messages=(AgentMessage(role="user", content="What is foo?"),),
                llm=llm,
                tools=(tool,),
                max_iterations=4,
                _config=KnotConfig(id="loop"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        response = run.outputs["loop"]
        assert isinstance(response, AgentResponse)
        assert response.finish_reason == "stop"
        assert response.content == "42 is the answer"
        assert tool.invocations == [{"input": "foo"}]

    async def test_falls_through_when_iterations_exhausted(self) -> None:
        llm = StubLLMProvider(["Still thinking about it..."])
        with Tapestry() as t:
            ReActLoop(
                messages=(AgentMessage(role="user", content="ponder"),),
                llm=llm,
                tools=(),
                max_iterations=2,
                _config=KnotConfig(id="loop"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        response = run.outputs["loop"]
        assert isinstance(response, AgentResponse)
        assert response.finish_reason == "length"
        assert "Still thinking" in response.content
