"""Tests for :class:`ToolChain`.

``ToolChain`` is a ``SubTapestry`` since PIR-856: ``process`` returns the sink
of an inner pipeline (one ``ToolInvocation`` per step, gated on the previous
step's success) rather than the result itself, so the outcome tests run a
real tapestry and read the chain's output. That is the behaviour under test —
the whole point of the change is that every step goes through the engine —
and asserting on a directly-awaited ``process`` would no longer exercise it.
The input-validation tests still call ``process`` directly, because the
guards fire before any knot is built (see
``tests/specializations/planning/test_tool_executor.py`` for the identical
pattern PIR-733 established for the single-call case).
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.agent.approval_hook import ApprovalHook
from pirn_agents.specializations.tool_use.tool_chain import ToolChain
from pirn_agents.testing.stub_tool import StubTool as KitStubTool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_permissions import ToolPermissions
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus
from tests.specializations.conftest import StubTool


class _DenyHook(ApprovalHook):
    async def request_approval(self, *, tool_name: str, arguments: Mapping[str, Any]) -> bool:
        return False


def _make_chain(initial_call: ToolCall, tools: list) -> ToolChain:
    with Tapestry():
        return ToolChain(
            initial_call=initial_call,
            tools=tools,
            _config=KnotConfig(id="chain"),
        )


async def _run_chain(initial_call: ToolCall, tools: list) -> ToolResult:
    """Run a ToolChain through a real Tapestry and return its output."""
    with Tapestry() as t:
        ToolChain(initial_call=initial_call, tools=tools, _config=KnotConfig(id="chain"))
    result = await t.run(RunRequest())
    assert result.succeeded, result.exceptions
    return result.outputs["chain"]


class TestToolChainValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_tools(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        chain = _make_chain(call, [StubTool(name="x")])
        with self.assertRaisesRegex(ValueError, "tools must not be empty"):
            await chain.process(initial_call=call, tools=[])

    async def test_rejects_non_tool(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        chain = _make_chain(call, [StubTool(name="x")])
        with self.assertRaisesRegex(TypeError, r"tools\[0\] must be a Tool"):
            await chain.process(initial_call=call, tools=["bad"])  # type: ignore[list-item]

    async def test_rejects_non_tool_call(self) -> None:
        tool = StubTool(name="step1", handler="result1")
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        chain = _make_chain(call, [tool])
        result = await chain({"initial_call": "not-a-call", "tools": [tool]})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"


class TestToolChainHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_executes_single_tool(self) -> None:
        tool = StubTool(name="step1", handler="result1")
        call = ToolCall(tool_name="step1", arguments={"input": "x"}, call_id="c1")
        result = await _run_chain(call, [tool])
        assert result.result == "result1"
        assert result.error is None

    async def test_pipes_output_as_input_through_chain(self) -> None:
        received_args: list[dict] = []

        def capture(args):  # type: ignore[no-untyped-def]
            received_args.append(dict(args))
            return f"processed:{args.get('input', '')}"

        tool1 = StubTool(name="step1", handler="first-output")
        tool2 = StubTool(name="step2", handler=capture)
        call = ToolCall(tool_name="step1", arguments={"input": "start"}, call_id="c1")
        result = await _run_chain(call, [tool1, tool2])
        assert result.result == "processed:first-output"
        assert received_args[0] == {"input": "first-output"}

    async def test_returns_error_on_tool_exception(self) -> None:
        def fail(args):  # type: ignore[no-untyped-def]
            raise ValueError("step exploded")

        tool = StubTool(name="explode", handler=fail)
        call = ToolCall(tool_name="explode", arguments={}, call_id="c1")
        result = await _run_chain(call, [tool])
        # PIR-856: the step now runs through ToolInvocation, which reports
        # "TypeName: message" (and scrubs credentials), matching
        # ToolExecutor's existing single-call fidelity, rather than the bare
        # str(exc) this class used to build inline.
        assert result.error == "ValueError: step exploded"

    async def test_call_id_is_preserved_across_every_step(self) -> None:
        tool1 = StubTool(name="step1", handler="a")
        tool2 = StubTool(name="step2", handler="b")
        call = ToolCall(tool_name="step1", arguments={}, call_id="original-id")
        result = await _run_chain(call, [tool1, tool2])
        assert result.call_id == "original-id"


class TestToolChainShortCircuits(unittest.IsolatedAsyncioTestCase):
    """PIR-856: a failing step must stop the chain — later tools never run."""

    async def test_a_failure_stops_the_chain_before_the_next_tool(self) -> None:
        def fail(args):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

        tool1 = StubTool(name="step1", handler=fail)
        tool2 = StubTool(name="step2", handler="never")
        call = ToolCall(tool_name="step1", arguments={}, call_id="c1")

        result = await _run_chain(call, [tool1, tool2])

        assert result.error == "RuntimeError: boom"
        assert tool2.invocations == []

    async def test_a_middle_failure_stops_a_three_tool_chain(self) -> None:
        def fail(args):  # type: ignore[no-untyped-def]
            raise RuntimeError("middle boom")

        tool1 = StubTool(name="step1", handler="ok1")
        tool2 = StubTool(name="step2", handler=fail)
        tool3 = StubTool(name="step3", handler="never")
        call = ToolCall(tool_name="step1", arguments={}, call_id="c1")

        result = await _run_chain(call, [tool1, tool2, tool3])

        assert result.error == "RuntimeError: middle boom"
        assert tool3.invocations == []


class TestRunsThroughTheEngine(unittest.IsolatedAsyncioTestCase):
    """PIR-856: each step is a node now, not an inline await."""

    async def test_each_step_gets_its_own_lineage_row(self) -> None:
        tool1 = StubTool(name="step1", handler="a")
        tool2 = StubTool(name="step2", handler="b")
        call = ToolCall(tool_name="step1", arguments={}, call_id="c1")
        with Tapestry() as t:
            ToolChain(initial_call=call, tools=[tool1, tool2], _config=KnotConfig(id="chain"))

        result = await t.run(RunRequest())

        assert result.succeeded
        children = await t.history.children_of(result.run_id)
        inner_knot_ids = {row.knot_id for child in children for row in child.lineage}
        assert "step-0" in inner_knot_ids
        assert "step-1" in inner_knot_ids


class TestToolChainApproval(unittest.IsolatedAsyncioTestCase):
    """PIR-865: a denied step skips as ``Skipped``, stopping the chain like any other skip."""

    async def test_denied_first_step_stops_the_chain_as_skipped(self) -> None:
        step1 = KitStubTool(name="step1", permissions=ToolPermissions(approval_required=True))
        step2 = KitStubTool(name="step2", result="unreachable")
        call = ToolCall(tool_name="step1", arguments={"input": "x"}, call_id="c1")
        with Tapestry() as t:
            ToolChain(
                initial_call=call,
                tools=[step1, step2],
                approval_hook=_DenyHook(),
                _config=KnotConfig(id="chain"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        view = result.outputs["chain"]
        assert view.status is ToolStatus.SKIPPED
        assert view.error == "call skipped: approval denied"
        assert step1.invocations == []
        assert step2.invocations == []

    async def test_approved_first_step_proceeds_to_the_next(self) -> None:
        step1 = KitStubTool(
            name="step1", permissions=ToolPermissions(approval_required=True), result="a"
        )
        step2 = KitStubTool(name="step2", handler=lambda args: args["input"] + "-b")
        call = ToolCall(tool_name="step1", arguments={"input": "x"}, call_id="c1")
        with Tapestry() as t:
            ToolChain(
                initial_call=call,
                tools=[step1, step2],
                approval_hook=None,
                _config=KnotConfig(id="chain"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        view = result.outputs["chain"]
        assert view.status is ToolStatus.OK
        assert view.result == "a-b"

    async def test_denied_second_step_is_labelled_approval_denied_too(self) -> None:
        step1 = KitStubTool(name="step1", result="a")
        step2 = KitStubTool(name="step2", permissions=ToolPermissions(approval_required=True))
        call = ToolCall(tool_name="step1", arguments={"input": "x"}, call_id="c1")
        with Tapestry() as t:
            ToolChain(
                initial_call=call,
                tools=[step1, step2],
                approval_hook=_DenyHook(),
                _config=KnotConfig(id="chain"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        view = result.outputs["chain"]
        assert view.status is ToolStatus.SKIPPED
        assert view.error == "call skipped: approval denied"
        assert step2.invocations == []
