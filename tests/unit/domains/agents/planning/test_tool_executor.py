"""Unit tests for :class:`ToolExecutor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn_agents.planning.tool_executor import ToolExecutor
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubTool


def _make_knot(tools: tuple) -> ToolExecutor:
    @knot
    async def _c() -> ToolCall:
        return ToolCall(tool_name="search", arguments={}, call_id="c1")

    with Tapestry():
        upstream = _c(_config=KnotConfig(id="c"))
        return ToolExecutor(call=upstream, tools=tools, _config=KnotConfig(id="x"))


_CALL = ToolCall(tool_name="search", arguments={"q": "x"}, call_id="c1")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_invokes_matching_tool(self) -> None:
        search = StubTool(name="search", handler="found")
        k = _make_knot((search,))
        out: ToolResult = await k.process(call=_CALL, tools=(search,))
        assert out.error is None
        assert out.result == "found"
        assert out.call_id == "c1"

    async def test_unknown_tool_yields_error_result(self) -> None:
        other = StubTool(name="other")
        k = _make_knot((other,))
        out: ToolResult = await k.process(call=_CALL, tools=(other,))
        assert out.error is not None
        assert "search" in out.error

    async def test_tool_exception_yields_error_result(self) -> None:
        def bad_handler(_: object) -> object:
            raise RuntimeError("boom")

        search = StubTool(name="search", handler=bad_handler)
        k = _make_knot((search,))
        out: ToolResult = await k.process(call=_CALL, tools=(search,))
        assert out.error is not None
        assert "boom" in out.error

    async def test_rejects_empty_tools(self) -> None:
        search = StubTool(name="search")
        k = _make_knot((search,))
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(call=_CALL, tools=())

    async def test_rejects_non_tool_call(self) -> None:
        search = StubTool(name="search")
        k = _make_knot((search,))
        with self.assertRaises(TypeError):
            await k.process(
                call="not a call",  # type: ignore[arg-type]
                tools=(search,),
            )
