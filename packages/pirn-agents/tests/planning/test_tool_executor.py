"""Unit tests for :class:`ToolExecutor`.

``ToolExecutor`` is a ``SubTapestry`` since PIR-733: ``process`` returns the sink
of an inner pipeline rather than the result itself, so the outcome tests run a
real tapestry and read the executor's output. That is the behaviour under test —
the whole point of the change is that the call goes through the engine — and
asserting on a directly-awaited ``process`` would no longer exercise it. The
input-validation tests still call ``process`` directly, because the guards fire
before any knot is built.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.planning.tool_executor import ToolExecutor
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_result import ToolResult
from tests.conftest import StubTool


def _make_knot(tools: tuple) -> ToolExecutor:
    @knot
    async def _c() -> ToolCall:
        return ToolCall(tool_name="search", arguments={}, call_id="c1")

    with Tapestry():
        upstream = _c(_config=KnotConfig(id="c"))
        return ToolExecutor(call=upstream, tools=tools, _config=KnotConfig(id="x"))


_CALL = ToolCall(tool_name="search", arguments={"q": "x"}, call_id="c1")


async def _execute(tools: tuple) -> ToolResult:
    """Run a ToolExecutor over ``_CALL`` through the engine and return its output."""

    @knot
    async def _call_source() -> ToolCall:
        return _CALL

    with Tapestry() as tapestry:
        upstream = _call_source(_config=KnotConfig(id="c"))
        ToolExecutor(call=upstream, tools=tools, _config=KnotConfig(id="x"))

    result = await tapestry.run(RunRequest())
    assert result.succeeded, result.exceptions
    return result.outputs["x"]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_invokes_matching_tool(self) -> None:
        search = StubTool(name="search", handler="found")
        out = await _execute((search,))
        assert out.error is None
        assert out.result == "found"
        assert out.call_id == "c1"

    async def test_unknown_tool_yields_error_result(self) -> None:
        other = StubTool(name="other")
        out = await _execute((other,))
        assert out.error is not None
        assert "search" in out.error

    async def test_tool_exception_yields_error_result(self) -> None:
        def bad_handler(_: object) -> object:
            raise RuntimeError("boom")

        search = StubTool(name="search", handler=bad_handler)
        out = await _execute((search,))
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


class TestRunsThroughTheEngine(unittest.IsolatedAsyncioTestCase):
    """PIR-733: the invocation is a node now, not an inline await."""

    async def test_the_invocation_gets_its_own_lineage_row(self) -> None:
        @knot
        async def _call_source() -> ToolCall:
            return _CALL

        with Tapestry() as tapestry:
            upstream = _call_source(_config=KnotConfig(id="c"))
            ToolExecutor(
                call=upstream,
                tools=(StubTool(name="search", handler="found"),),
                _config=KnotConfig(id="x"),
            )

        result = await tapestry.run(RunRequest())

        # The executor is a SubTapestry, so the invocation is recorded in the
        # inner run rather than beside the executor in the outer one.
        children = await tapestry.history.children_of(result.run_id)
        inner_knot_ids = {row.knot_id for child in children for row in child.lineage}
        assert "invoke" in inner_knot_ids, inner_knot_ids
