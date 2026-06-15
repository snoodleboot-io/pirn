"""Unit tests for :class:`ToolRouter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn_agents.planning.tool_router import ToolRouter
from pirn_agents.types.tool_call import ToolCall
from pirn.tapestry import Tapestry

from tests.unit.domains.agents.conftest import StubTool


def _make_knot(tools: tuple) -> ToolRouter:
    @knot
    async def _s() -> str:
        return "step"

    with Tapestry():
        upstream = _s(_config=KnotConfig(id="s"))
        return ToolRouter(step=upstream, tools=tools, _config=KnotConfig(id="r"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_routes_step_to_matching_tool(self) -> None:
        search = StubTool(name="search", description="search engine")
        calc = StubTool(name="calc", description="calculator")
        k = _make_knot((search, calc))
        call: ToolCall = await k.process(
            step="use search to find flights",
            tools=(search, calc),
        )
        assert call.tool_name == "search"
        assert call.arguments == {"step": "use search to find flights"}

    async def test_raises_when_no_match(self) -> None:
        search = StubTool(name="search")
        k = _make_knot((search,))
        with self.assertRaises(ValueError):
            await k.process(step="do something else", tools=(search,))

    async def test_rejects_empty_tool_list(self) -> None:
        search = StubTool(name="search")
        k = _make_knot((search,))
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(step="use search", tools=())

    async def test_rejects_empty_step(self) -> None:
        search = StubTool(name="search")
        k = _make_knot((search,))
        with self.assertRaises(ValueError):
            await k.process(step="", tools=(search,))
