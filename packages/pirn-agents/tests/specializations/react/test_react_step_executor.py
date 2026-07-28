"""Tests for :class:`ReActStepExecutor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.input.context_builder import ContextBuilder
from pirn_agents.specializations.react.messages_passthrough import (
    MessagesPassthrough,
)
from pirn_agents.specializations.react.react_step_executor import (
    ReActStepExecutor,
)
from pirn_agents.types.messaging.agent_message import AgentMessage
from tests.specializations.conftest import (
    StubLLMProvider,
    StubTool,
)


class TestReActStepExecutorProcess(unittest.IsolatedAsyncioTestCase):
    def _make(self, llm: StubLLMProvider, tools: tuple = ()) -> ReActStepExecutor:
        with Tapestry():
            seed = MessagesPassthrough(
                messages=(AgentMessage(role="user", content="hi"),),
                _config=KnotConfig(id="seed"),
            )
            ctx = ContextBuilder(messages=seed, _config=KnotConfig(id="ctx"))
            return ReActStepExecutor(
                context=ctx,
                llm=llm,
                tools=tools,
                already_terminated=False,
                _config=KnotConfig(id="step"),
            )

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["Final Answer: done"])
        knot = self._make(llm)
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await knot.process(
                context=[AgentMessage(role="user", content="hi")],
                llm="not-a-provider",  # type: ignore[arg-type]
                tools=(),
                already_terminated=False,
            )

    async def test_rejects_non_tool(self) -> None:
        llm = StubLLMProvider(["Final Answer: done"])
        knot = self._make(llm)
        with self.assertRaisesRegex(TypeError, "tools\\[0\\] must be a Tool"):
            await knot.process(
                context=[AgentMessage(role="user", content="hi")],
                llm=llm,
                tools=("not-a-tool",),  # type: ignore[arg-type]
                already_terminated=False,
            )

    async def test_final_answer_short_circuits_tool_call(self) -> None:
        llm = StubLLMProvider(["Final Answer: 42"])
        tool = StubTool(name="search", handler="result")
        knot = self._make(llm, tools=(tool,))
        context = [AgentMessage(role="user", content="What?")]
        emitted = await knot.process(
            context=context, llm=llm, tools=(tool,), already_terminated=False
        )
        assert len(emitted) == 1
        assert emitted[0].role == "assistant"
        assert "Final Answer:" in emitted[0].content
        assert tool.invocations == []

    async def test_action_invokes_tool_and_records_observation(self) -> None:
        llm = StubLLMProvider(["Action: search\nAction Input: quantum computing"])
        tool = StubTool(name="search", handler="qubits are stable")
        knot = self._make(llm, tools=(tool,))
        context = [AgentMessage(role="user", content="research")]
        emitted = await knot.process(
            context=context, llm=llm, tools=(tool,), already_terminated=False
        )
        assert len(emitted) == 3
        thought, call, observation = emitted
        assert thought.role == "assistant"
        assert call.role == "assistant"
        assert call.name == "search"
        assert observation.role == "tool"
        assert observation.content == "qubits are stable"
        assert tool.invocations == [{"input": "quantum computing"}]

    async def test_already_terminated_makes_no_llm_call(self) -> None:
        """The PIR-753 cost defect: a post-termination step must not pay for a call."""
        llm = StubLLMProvider(["should never be requested"])
        tool = StubTool(name="search", handler="result")
        knot = self._make(llm, tools=(tool,))
        context = [AgentMessage(role="user", content="What?")]
        emitted = await knot.process(
            context=context, llm=llm, tools=(tool,), already_terminated=True
        )
        assert emitted == ()
        assert llm.calls == []
        assert tool.invocations == []

    async def test_already_terminated_still_validates_its_inputs(self) -> None:
        """Short-circuiting must not weaken the type contract."""
        llm = StubLLMProvider(["unused"])
        knot = self._make(llm)
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await knot.process(
                context=[AgentMessage(role="user", content="hi")],
                llm="not-a-provider",  # type: ignore[arg-type]
                tools=(),
                already_terminated=True,
            )
