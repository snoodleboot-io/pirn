"""Tests for :class:`ReActStepExecutor`.

``ReActStepExecutor`` is a ``SubTapestry`` since PIR-856: when a thought
selects a registered tool, ``process`` returns the sink of an inner pipeline
(a ``ToolInvocation`` plus its assembler) rather than the messages
themselves, so those outcome tests run a real tapestry and read the step's
output. That is the behaviour under test — the whole point of the change is
that the tool call goes through the engine — and asserting on a
directly-awaited ``process`` would no longer exercise it. The
input-validation tests, and the branches that need no tool call, still call
``process`` directly: the guards fire, and the no-tool-call terminals are
built, before any further graph is involved (see
``tests/specializations/planning/test_tool_executor.py`` for the identical
pattern PIR-733 established for the single-call case).
"""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
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


def _make(llm: StubLLMProvider, tools: tuple = ()) -> ReActStepExecutor:
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


async def _run_step(
    llm: StubLLMProvider,
    tools: tuple,
    context: list[AgentMessage],
    already_terminated: bool,
) -> tuple[AgentMessage, ...]:
    """Wire a ReActStepExecutor over a real context/seed and run it end to end."""
    with Tapestry() as t:
        seed = MessagesPassthrough(messages=tuple(context), _config=KnotConfig(id="seed"))
        ctx = ContextBuilder(messages=seed, _config=KnotConfig(id="ctx"))
        ReActStepExecutor(
            context=ctx,
            llm=llm,
            tools=tools,
            already_terminated=already_terminated,
            _config=KnotConfig(id="step"),
        )
    result = await t.run(RunRequest())
    assert result.succeeded, result.exceptions
    return result.outputs["step"]


class TestReActStepExecutorProcess(unittest.IsolatedAsyncioTestCase):
    def _make(self, llm: StubLLMProvider, tools: tuple = ()) -> ReActStepExecutor:
        return _make(llm, tools)

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["Final Answer: done"])
        knot = self._make(llm)
        result = await knot(
            {
                "context": [AgentMessage(role="user", content="hi")],
                "llm": "not-a-provider",
                "tools": (),
                "already_terminated": False,
            }
        )
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

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
        context = [AgentMessage(role="user", content="What?")]
        emitted = await _run_step(llm, (tool,), context, already_terminated=False)
        assert len(emitted) == 1
        assert emitted[0].role == "assistant"
        assert "Final Answer:" in emitted[0].content
        assert tool.invocations == []

    async def test_action_invokes_tool_and_records_observation(self) -> None:
        llm = StubLLMProvider(["Action: search\nAction Input: quantum computing"])
        tool = StubTool(name="search", handler="qubits are stable")
        context = [AgentMessage(role="user", content="research")]
        emitted = await _run_step(llm, (tool,), context, already_terminated=False)
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
        context = [AgentMessage(role="user", content="What?")]
        emitted = await _run_step(llm, (tool,), context, already_terminated=True)
        assert emitted == ()
        assert llm.calls == []
        assert tool.invocations == []

    async def test_already_terminated_still_validates_its_inputs(self) -> None:
        """Short-circuiting must not weaken the type contract."""
        llm = StubLLMProvider(["unused"])
        knot = self._make(llm)
        result = await knot(
            {
                "context": [AgentMessage(role="user", content="hi")],
                "llm": "not-a-provider",
                "tools": (),
                "already_terminated": True,
            }
        )
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_unregistered_action_reports_without_invoking_anything(self) -> None:
        """No matching tool means nothing to invoke — a direct terminal, not a ToolInvocation."""
        llm = StubLLMProvider(["Action: missing\nAction Input: x"])
        registered = StubTool(name="search", handler="result")
        context = [AgentMessage(role="user", content="What?")]
        emitted = await _run_step(llm, (registered,), context, already_terminated=False)
        assert len(emitted) == 3
        observation = emitted[2]
        assert observation.role == "tool"
        assert "missing" in observation.content
        assert "not registered" in observation.content
        assert registered.invocations == []

    async def test_a_raising_tool_reports_a_scrubbed_error_observation(self) -> None:
        """PIR-856: routed through ToolInvocation now, so failures are scrubbed."""

        def raise_error(_args):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

        llm = StubLLMProvider(["Action: search\nAction Input: x"])
        tool = StubTool(name="search", handler=raise_error)
        context = [AgentMessage(role="user", content="What?")]
        emitted = await _run_step(llm, (tool,), context, already_terminated=False)
        observation = emitted[2]
        assert observation.role == "tool"
        assert observation.content == "RuntimeError: boom"


class TestRunsThroughTheEngine(unittest.IsolatedAsyncioTestCase):
    """PIR-856: a selected tool call is a node now, not an inline await."""

    async def test_the_invocation_gets_its_own_lineage_row(self) -> None:
        llm = StubLLMProvider(["Action: search\nAction Input: q"])
        tool = StubTool(name="search", handler="found")
        with Tapestry() as t:
            seed = MessagesPassthrough(
                messages=(AgentMessage(role="user", content="hi"),),
                _config=KnotConfig(id="seed"),
            )
            ctx = ContextBuilder(messages=seed, _config=KnotConfig(id="ctx"))
            ReActStepExecutor(
                context=ctx,
                llm=llm,
                tools=(tool,),
                already_terminated=False,
                _config=KnotConfig(id="step"),
            )

        result = await t.run(RunRequest())

        assert result.succeeded
        children = await t.history.children_of(result.run_id)
        inner_knot_ids = {row.knot_id for child in children for row in child.lineage}
        assert "tool-call" in inner_knot_ids, inner_knot_ids
