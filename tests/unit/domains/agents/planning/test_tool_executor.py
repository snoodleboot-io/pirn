"""Unit tests for :class:`ToolExecutor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.planning.tool_executor import ToolExecutor
from pirn.domains.agents.types.tool_call import ToolCall
from pirn.domains.agents.types.tool_result import ToolResult
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubTool


@knot
async def emit_call() -> ToolCall:
    return ToolCall(tool_name="search", arguments={"q": "x"}, call_id="c1")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_invokes_matching_tool(self) -> None:
        search = StubTool(name="search", handler="found")
        with Tapestry() as t:
            call = emit_call(_config=KnotConfig(id="c"))
            ToolExecutor(call=call, tools=(search,), _config=KnotConfig(id="x"))
        result = await t.run(RunRequest())
        out: ToolResult = result.outputs["x"]
        assert out.error is None
        assert out.result == "found"
        assert out.call_id == "c1"

    async def test_unknown_tool_yields_error_result(self) -> None:
        other = StubTool(name="other")
        with Tapestry() as t:
            call = emit_call(_config=KnotConfig(id="c"))
            ToolExecutor(call=call, tools=(other,), _config=KnotConfig(id="x"))
        result = await t.run(RunRequest())
        out: ToolResult = result.outputs["x"]
        assert out.error is not None
        assert "search" in out.error

    async def test_tool_exception_yields_error_result(self) -> None:
        def bad_handler(_: object) -> object:
            raise RuntimeError("boom")

        search = StubTool(name="search", handler=bad_handler)
        with Tapestry() as t:
            call = emit_call(_config=KnotConfig(id="c"))
            ToolExecutor(call=call, tools=(search,), _config=KnotConfig(id="x"))
        result = await t.run(RunRequest())
        out: ToolResult = result.outputs["x"]
        assert out.error is not None
        assert "boom" in out.error


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_tools(self) -> None:
        @knot
        async def c() -> ToolCall:
            return ToolCall(tool_name="x", arguments={}, call_id="x")

        with Tapestry():
            cc = c(_config=KnotConfig(id="c"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                ToolExecutor(call=cc, tools=(), _config=KnotConfig(id="x"))
