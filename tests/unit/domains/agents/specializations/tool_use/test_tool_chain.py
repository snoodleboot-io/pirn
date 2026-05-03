"""Tests for :class:`ToolChain`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.tool_use.tool_chain import ToolChain
from pirn.domains.agents.types.tool_call import ToolCall
from pirn.domains.agents.types.tool_result import ToolResult
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubTool


@pytest.mark.asyncio
class TestToolChainConstruction:
    async def test_rejects_empty_tools(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        with pytest.raises(ValueError, match="tools must not be empty"):
            with Tapestry():
                ToolChain(
                    initial_call=call,
                    tools=[],
                    _config=KnotConfig(id="chain"),
                )

    async def test_rejects_non_tool(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        with pytest.raises(TypeError, match=r"tools\[0\] must be a Tool"):
            with Tapestry():
                ToolChain(
                    initial_call=call,
                    tools=["bad"],  # type: ignore[list-item]
                    _config=KnotConfig(id="chain"),
                )


@pytest.mark.asyncio
class TestToolChainHappyPath:
    async def test_executes_single_tool(self) -> None:
        tool = StubTool(name="step1", handler="result1")
        call = ToolCall(tool_name="step1", arguments={"input": "x"}, call_id="c1")
        with Tapestry() as t:
            ToolChain(
                initial_call=call,
                tools=[tool],
                _config=KnotConfig(id="chain"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        final: ToolResult = result.outputs["chain"]
        assert final.result == "result1"
        assert final.error is None

    async def test_pipes_output_as_input_through_chain(self) -> None:
        received_args: list[dict] = []

        def capture(args):  # type: ignore[no-untyped-def]
            received_args.append(dict(args))
            return f"processed:{args.get('input', '')}"

        tool1 = StubTool(name="step1", handler="first-output")
        tool2 = StubTool(name="step2", handler=capture)
        call = ToolCall(tool_name="step1", arguments={"input": "start"}, call_id="c1")
        with Tapestry() as t:
            ToolChain(
                initial_call=call,
                tools=[tool1, tool2],
                _config=KnotConfig(id="chain"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        final: ToolResult = result.outputs["chain"]
        assert final.result == "processed:first-output"
        assert received_args[0] == {"input": "first-output"}

    async def test_returns_error_on_tool_exception(self) -> None:
        def fail(args):  # type: ignore[no-untyped-def]
            raise ValueError("step exploded")

        tool = StubTool(name="explode", handler=fail)
        call = ToolCall(tool_name="explode", arguments={}, call_id="c1")
        with Tapestry() as t:
            ToolChain(
                initial_call=call,
                tools=[tool],
                _config=KnotConfig(id="chain"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        final: ToolResult = result.outputs["chain"]
        assert final.error == "step exploded"
