"""Tests for :class:`ToolResultFormatter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.tool_use.tool_result_formatter import (
    ToolResultFormatter,
)
from pirn.domains.agents.types.tool_result import ToolResult
from pirn.tapestry import Tapestry


def _make_formatter(tool_result: ToolResult) -> ToolResultFormatter:
    with Tapestry():
        return ToolResultFormatter(
            tool_result=tool_result,
            _config=KnotConfig(id="fmt"),
        )


class TestToolResultFormatterHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_formats_successful_string_result(self) -> None:
        tool_result = ToolResult(call_id="c1", result="42 apples")
        fmt = _make_formatter(tool_result)
        formatted: str = await fmt.process(tool_result=tool_result)
        assert isinstance(formatted, str)
        assert "c1" in formatted
        assert "42 apples" in formatted

    async def test_formats_dict_result_as_json(self) -> None:
        tool_result = ToolResult(call_id="c2", result={"key": "value"})
        fmt = _make_formatter(tool_result)
        formatted: str = await fmt.process(tool_result=tool_result)
        assert "key" in formatted
        assert "value" in formatted

    async def test_formats_error_result(self) -> None:
        tool_result = ToolResult(call_id="c3", result=None, error="connection refused")
        fmt = _make_formatter(tool_result)
        formatted: str = await fmt.process(tool_result=tool_result)
        assert "c3" in formatted
        assert "connection refused" in formatted
        assert "failed" in formatted.lower()

    async def test_rejects_non_tool_result(self) -> None:
        tool_result = ToolResult(call_id="c1", result="x")
        fmt = _make_formatter(tool_result)
        with self.assertRaisesRegex(TypeError, "tool_result"):
            await fmt.process(tool_result="not-a-result")  # type: ignore[arg-type]

    async def test_formats_list_result_as_json(self) -> None:
        tool_result = ToolResult(call_id="c4", result=[1, 2, 3])
        fmt = _make_formatter(tool_result)
        formatted: str = await fmt.process(tool_result=tool_result)
        assert "1" in formatted
        assert "2" in formatted
