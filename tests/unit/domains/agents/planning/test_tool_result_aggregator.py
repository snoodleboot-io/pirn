"""Unit tests for :class:`ToolResultAggregator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn_agents.planning.tool_result_aggregator import ToolResultAggregator
from pirn_agents.types.tool_result import ToolResult
from pirn.tapestry import Tapestry


def _make_knot() -> ToolResultAggregator:
    @knot
    async def _r() -> tuple:
        return ()

    with Tapestry():
        upstream = _r(_config=KnotConfig(id="r"))
        return ToolResultAggregator(results=upstream, _config=KnotConfig(id="agg"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_aggregates_success_and_failure(self) -> None:
        k = _make_knot()
        out = await k.process(
            results=(
                ToolResult(call_id="a", result={"answer": 1}, error=None),
                ToolResult(call_id="b", result=None, error="boom"),
            )
        )
        assert out["a"] == {"answer": 1}
        assert out["b"] == {"error": "boom"}

    async def test_empty_results_returns_empty_dict(self) -> None:
        k = _make_knot()
        out = await k.process(results=())
        assert out == {}

    async def test_rejects_non_tool_result_entries(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(results=("not-a-result",))  # type: ignore[arg-type]
