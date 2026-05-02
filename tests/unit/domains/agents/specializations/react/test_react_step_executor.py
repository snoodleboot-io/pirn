"""Tests for :class:`ReActStepExecutor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.react.messages_passthrough import (
    MessagesPassthrough,
)
from pirn.domains.agents.specializations.react.react_step_executor import (
    ReActStepExecutor,
)
from pirn.domains.agents.input.context_builder import ContextBuilder
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubTool,
)


@pytest.mark.asyncio
class TestReActStepExecutorConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                seed = MessagesPassthrough(
                    messages=(AgentMessage(role="user", content="hi"),),
                    _config=KnotConfig(id="seed"),
                )
                ctx = ContextBuilder(messages=seed, _config=KnotConfig(id="ctx"))
                ReActStepExecutor(
                    context=ctx,
                    llm="not-a-provider",  # type: ignore[arg-type]
                    tools=(),
                    _config=KnotConfig(id="step"),
                )

    async def test_rejects_non_tool(self) -> None:
        llm = StubLLMProvider(["Final Answer: done"])
        with pytest.raises(TypeError, match="tools\\[0\\] must be a Tool"):
            with Tapestry():
                seed = MessagesPassthrough(
                    messages=(AgentMessage(role="user", content="hi"),),
                    _config=KnotConfig(id="seed"),
                )
                ctx = ContextBuilder(messages=seed, _config=KnotConfig(id="ctx"))
                ReActStepExecutor(
                    context=ctx,
                    llm=llm,
                    tools=("not-a-tool",),  # type: ignore[arg-type]
                    _config=KnotConfig(id="step"),
                )


@pytest.mark.asyncio
class TestReActStepExecutorHappyPath:
    async def test_final_answer_short_circuits_tool_call(self) -> None:
        llm = StubLLMProvider(["Final Answer: 42"])
        tool = StubTool(name="search", handler="result")
        with Tapestry() as t:
            seed = MessagesPassthrough(
                messages=(AgentMessage(role="user", content="What?"),),
                _config=KnotConfig(id="seed"),
            )
            ctx = ContextBuilder(messages=seed, _config=KnotConfig(id="ctx"))
            ReActStepExecutor(
                context=ctx,
                llm=llm,
                tools=(tool,),
                _config=KnotConfig(id="step"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        emitted = result.outputs["step"]
        assert len(emitted) == 1
        assert emitted[0].role == "assistant"
        assert "Final Answer:" in emitted[0].content
        assert tool.invocations == []

    async def test_action_invokes_tool_and_records_observation(self) -> None:
        llm = StubLLMProvider(
            ["Action: search\nAction Input: quantum computing"]
        )
        tool = StubTool(name="search", handler="qubits are stable")
        with Tapestry() as t:
            seed = MessagesPassthrough(
                messages=(AgentMessage(role="user", content="research"),),
                _config=KnotConfig(id="seed"),
            )
            ctx = ContextBuilder(messages=seed, _config=KnotConfig(id="ctx"))
            ReActStepExecutor(
                context=ctx,
                llm=llm,
                tools=(tool,),
                _config=KnotConfig(id="step"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        emitted = result.outputs["step"]
        assert len(emitted) == 3
        thought, call, observation = emitted
        assert thought.role == "assistant"
        assert call.role == "assistant"
        assert call.name == "search"
        assert observation.role == "tool"
        assert observation.content == "qubits are stable"
        assert tool.invocations == [{"input": "quantum computing"}]
