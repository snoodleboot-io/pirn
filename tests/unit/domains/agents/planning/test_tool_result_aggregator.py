"""Unit tests for :class:`ToolResultAggregator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.planning.tool_result_aggregator import (
    ToolResultAggregator,
)
from pirn.domains.agents.types.tool_result import ToolResult
from pirn.tapestry import Tapestry


@knot
async def emit_results() -> tuple[ToolResult, ...]:
    return (
        ToolResult(call_id="a", result={"answer": 1}, error=None),
        ToolResult(call_id="b", result=None, error="boom"),
    )


@pytest.mark.asyncio
class TestProcess:
    async def test_aggregates_success_and_failure(self) -> None:
        with Tapestry() as t:
            r = emit_results(_config=KnotConfig(id="r"))
            ToolResultAggregator(results=r, _config=KnotConfig(id="agg"))
        result = await t.run(RunRequest())
        out = result.outputs["agg"]
        assert out["a"] == {"answer": 1}
        assert out["b"] == {"error": "boom"}

    async def test_rejects_non_tool_result_entries(self) -> None:
        @knot
        async def bad() -> tuple:
            return ("not-a-result",)

        with Tapestry() as t:
            r = bad(_config=KnotConfig(id="r"))
            ToolResultAggregator(results=r, _config=KnotConfig(id="agg"))
        result = await t.run(RunRequest())
        assert "agg" not in result.outputs
