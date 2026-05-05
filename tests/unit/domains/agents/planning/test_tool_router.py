"""Unit tests for :class:`ToolRouter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.planning.tool_router import ToolRouter
from pirn.domains.agents.types.tool_call import ToolCall
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubTool


@knot
async def emit_step() -> str:
    return "use search to find flights"


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_routes_step_to_matching_tool(self) -> None:
        search = StubTool(name="search", description="search engine")
        calc = StubTool(name="calc", description="calculator")
        with Tapestry() as t:
            step = emit_step(_config=KnotConfig(id="s"))
            ToolRouter(
                step=step,
                tools=(search, calc),
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        call: ToolCall = result.outputs["r"]
        assert call.tool_name == "search"
        assert call.arguments == {"step": "use search to find flights"}

    async def test_raises_when_no_match(self) -> None:
        @knot
        async def step() -> str:
            return "do something else"

        search = StubTool(name="search")
        with Tapestry() as t:
            s = step(_config=KnotConfig(id="s"))
            ToolRouter(step=s, tools=(search,), _config=KnotConfig(id="r"))
        result = await t.run(RunRequest())
        assert "r" not in result.outputs


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_tool_list(self) -> None:
        @knot
        async def step() -> str:
            return "x"

        with Tapestry():
            s = step(_config=KnotConfig(id="s"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                ToolRouter(step=s, tools=(), _config=KnotConfig(id="r"))

    def test_rejects_non_tool_entries(self) -> None:
        @knot
        async def step() -> str:
            return "x"

        with Tapestry():
            s = step(_config=KnotConfig(id="s"))
            with self.assertRaisesRegex(TypeError, "Tool"):
                ToolRouter(
                    step=s,
                    tools=("not-a-tool",),  # type: ignore[arg-type]
                    _config=KnotConfig(id="r"),
                )
