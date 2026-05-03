"""Tests for :class:`ParallelToolCaller`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.tool_use.parallel_tool_caller import (
    ParallelToolCaller,
)
from pirn.domains.agents.types.tool_call import ToolCall
from pirn.domains.agents.types.tool_result import ToolResult
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubTool


@pytest.mark.asyncio
class TestParallelToolCallerConstruction:
    async def test_rejects_non_tool_in_list(self) -> None:
        with pytest.raises(TypeError, match=r"tools\[0\] must be a Tool"):
            with Tapestry():
                ParallelToolCaller(
                    tool_calls=[],
                    tools=["bad"],  # type: ignore[list-item]
                    _config=KnotConfig(id="par"),
                )


@pytest.mark.asyncio
class TestParallelToolCallerHappyPath:
    async def test_invokes_all_tools_in_parallel(self) -> None:
        search = StubTool(name="search", handler="search-result")
        calc = StubTool(name="calc", handler="42")
        calls = [
            ToolCall(tool_name="search", arguments={"q": "news"}, call_id="c1"),
            ToolCall(tool_name="calc", arguments={"expr": "6*7"}, call_id="c2"),
        ]
        with Tapestry() as t:
            ParallelToolCaller(
                tool_calls=calls,
                tools=[search, calc],
                _config=KnotConfig(id="par"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        results: list[ToolResult] = result.outputs["par"]
        assert len(results) == 2
        by_id = {r.call_id: r for r in results}
        assert by_id["c1"].result == "search-result"
        assert by_id["c2"].result == "42"
        assert by_id["c1"].error is None
        assert by_id["c2"].error is None

    async def test_returns_error_for_unknown_tool(self) -> None:
        calls = [
            ToolCall(tool_name="nonexistent", arguments={}, call_id="cx"),
        ]
        with Tapestry() as t:
            ParallelToolCaller(
                tool_calls=calls,
                tools=[StubTool(name="other")],
                _config=KnotConfig(id="par"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        results: list[ToolResult] = result.outputs["par"]
        assert len(results) == 1
        assert results[0].error is not None
        assert "nonexistent" in results[0].error

    async def test_returns_error_on_tool_exception(self) -> None:
        def raise_error(args):  # type: ignore[no-untyped-def]
            raise RuntimeError("tool failed")

        bad_tool = StubTool(name="bad", handler=raise_error)
        calls = [ToolCall(tool_name="bad", arguments={}, call_id="c3")]
        with Tapestry() as t:
            ParallelToolCaller(
                tool_calls=calls,
                tools=[bad_tool],
                _config=KnotConfig(id="par"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        results: list[ToolResult] = result.outputs["par"]
        assert results[0].error == "tool failed"
