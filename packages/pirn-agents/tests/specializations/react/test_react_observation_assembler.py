"""Behaviour tests for ``ReActObservationAssembler`` and the step's branch terminals.

``ReActStepExecutor`` built its two inner terminals from module-level
``@KnotFactory.knot`` coroutines (PIR-873). ``KnotFactory`` generates a ``Knot``
subclass whose ``__name__`` is the *function's* name, so run history recorded
each one as ``_observation_assembler`` / ``_constant_messages`` — private names
no operator can look up, no module to import them from, and nothing the
registry's uniqueness check can see. They are now a real knot class in its own
module and a core ``Parameter``.

The lineage assertions below read the class names an operator actually sees in
history, and the standalone ``process()`` calls exercise the Rule 2 contract
that a knot's ``process`` is callable with plain values.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.run_request import RunRequest
from pirn.managers.exception_record import ExceptionRecord
from pirn.tapestry import Tapestry

from pirn_agents.specializations.react.react_observation_assembler import (
    ReActObservationAssembler,
)
from pirn_agents.specializations.react.react_step_executor import ReActStepExecutor
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.types.messaging.agent_message import AgentMessage
from tests.specializations.conftest import StubLLMProvider


def _assembler() -> ReActObservationAssembler:
    with Tapestry():
        return ReActObservationAssembler(
            thought=AgentMessage(role="assistant", content="thinking"),
            tool_call_message=AgentMessage(role="assistant", content="calling"),
            call_id="c1",
            action_name="search",
            outcome=Ok(value="unused"),
            _config=KnotConfig(id="assemble"),
        )


class TestReActObservationAssemblerProcess(unittest.IsolatedAsyncioTestCase):
    """The assembler is a knot whose ``process`` runs on plain values."""

    _thought = AgentMessage(role="assistant", content="thinking")
    _call = AgentMessage(role="assistant", content="calling")

    async def _run(self, outcome: Any) -> tuple[AgentMessage, ...]:
        return await _assembler().process(
            thought=self._thought,
            tool_call_message=self._call,
            call_id="c1",
            action_name="search",
            outcome=outcome,
        )

    async def test_ok_renders_the_tool_value_as_the_observation(self) -> None:
        messages = await self._run(Ok(value="Paris"))
        assert [message.role for message in messages] == ["assistant", "assistant", "tool"]
        assert messages[2].content == "Paris"
        assert messages[2].tool_call_id == "c1"
        assert messages[2].name == "search"

    async def test_err_renders_the_failure_message(self) -> None:
        record = ExceptionRecord(
            run_id="r1",
            knot_id="c1",
            exc_type="RuntimeError",
            message="tool exploded",
            traceback_text="Traceback...",
        )
        messages = await self._run(Err(record=record))
        assert "tool exploded" in messages[2].content

    async def test_the_thought_and_call_surrogate_pass_through(self) -> None:
        messages = await self._run(Ok(value="x"))
        assert messages[0] is self._thought
        assert messages[1] is self._call


class TestReActStepBranchesAreNamedInHistory(unittest.IsolatedAsyncioTestCase):
    """Every branch terminal is a knot class an operator can look up."""

    @staticmethod
    async def _inner_classes(llm: StubLLMProvider, tools: tuple[Any, ...]) -> dict[str, str]:
        history = InMemoryHistory()
        with Tapestry(history=history) as tapestry:
            ReActStepExecutor(
                context=(),
                llm=llm,
                tools=tools,
                already_terminated=False,
                _config=KnotConfig(id="step"),
            )
        run = await tapestry.run(RunRequest())
        assert run.succeeded, run.exceptions
        row = next(entry for entry in run.lineage if entry.knot_id == "step")
        inner = await history.get_run(row.extra["inner_run_id"])
        return {entry.knot_id: entry.knot_class for entry in inner.lineage}

    async def test_a_final_answer_branch_is_a_parameter(self) -> None:
        classes = await self._inner_classes(StubLLMProvider(["Final Answer: Paris"]), ())
        assert classes["final-answer"].endswith("Parameter"), classes

    async def test_a_no_action_branch_is_a_parameter(self) -> None:
        classes = await self._inner_classes(StubLLMProvider(["just musing"]), ())
        assert classes["no-action"].endswith("Parameter"), classes

    async def test_an_unregistered_tool_branch_is_a_parameter(self) -> None:
        classes = await self._inner_classes(StubLLMProvider(["Action: nope\nAction Input: x"]), ())
        assert classes["tool-not-registered"].endswith("Parameter"), classes

    async def test_the_assembler_branch_names_its_own_class(self) -> None:
        tool = StubTool(name="search", description="search", result="Paris")
        classes = await self._inner_classes(
            StubLLMProvider(["Action: search\nAction Input: capital of France"]), (tool,)
        )
        assert classes["assemble"].endswith("ReActObservationAssembler"), classes


if __name__ == "__main__":
    unittest.main()
