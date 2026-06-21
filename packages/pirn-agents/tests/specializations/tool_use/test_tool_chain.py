"""Tests for :class:`ToolChain`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.tool_use.tool_chain import ToolChain
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult
from pirn.tapestry import Tapestry

from tests.specializations.conftest import StubTool


def _make_chain(initial_call: ToolCall, tools: list) -> ToolChain:
    with Tapestry():
        return ToolChain(
            initial_call=initial_call,
            tools=tools,
            _config=KnotConfig(id="chain"),
        )


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
        with self.assertRaisesRegex(TypeError, "initial_call must be a ToolCall"):
            await chain.process(initial_call="not-a-call", tools=[tool])  # type: ignore[arg-type]


class TestToolChainHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_executes_single_tool(self) -> None:
        tool = StubTool(name="step1", handler="result1")
        call = ToolCall(tool_name="step1", arguments={"input": "x"}, call_id="c1")
        chain = _make_chain(call, [tool])
        result: ToolResult = await chain.process(initial_call=call, tools=[tool])
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
        chain = _make_chain(call, [tool1, tool2])
        result: ToolResult = await chain.process(initial_call=call, tools=[tool1, tool2])
        assert result.result == "processed:first-output"
        assert received_args[0] == {"input": "first-output"}

    async def test_returns_error_on_tool_exception(self) -> None:
        def fail(args):  # type: ignore[no-untyped-def]
            raise ValueError("step exploded")

        tool = StubTool(name="explode", handler=fail)
        call = ToolCall(tool_name="explode", arguments={}, call_id="c1")
        chain = _make_chain(call, [tool])
        result: ToolResult = await chain.process(initial_call=call, tools=[tool])
        assert result.error == "step exploded"
