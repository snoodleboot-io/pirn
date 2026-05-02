"""Tests for :class:`ReActLoop`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.react.react_loop import ReActLoop
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubTool,
)


@pytest.mark.asyncio
class TestReActLoopConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                ReActLoop(
                    messages=(AgentMessage(role="user", content="hi"),),
                    llm="not-a-provider",  # type: ignore[arg-type]
                    tools=(),
                    _config=KnotConfig(id="loop"),
                )

    async def test_rejects_zero_max_iterations(self) -> None:
        llm = StubLLMProvider(["Final Answer: ok"])
        with pytest.raises(ValueError, match="max_iterations"):
            with Tapestry():
                ReActLoop(
                    messages=(AgentMessage(role="user", content="hi"),),
                    llm=llm,
                    tools=(),
                    max_iterations=0,
                    _config=KnotConfig(id="loop"),
                )


@pytest.mark.asyncio
class TestReActLoopHappyPath:
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
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["loop"]
        assert isinstance(response, AgentResponse)
        assert response.finish_reason == "stop"
        assert response.content == "42 is the answer"
        assert tool.invocations == [{"input": "foo"}]

    async def test_falls_through_when_iterations_exhausted(self) -> None:
        # Every step emits a non-final assistant message that does not
        # match a tool name; the loop should run until max_iterations.
        llm = StubLLMProvider(["Still thinking about it..."])
        with Tapestry() as t:
            ReActLoop(
                messages=(AgentMessage(role="user", content="ponder"),),
                llm=llm,
                tools=(),
                max_iterations=2,
                _config=KnotConfig(id="loop"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["loop"]
        assert isinstance(response, AgentResponse)
        assert response.finish_reason == "length"
        assert "Still thinking" in response.content
