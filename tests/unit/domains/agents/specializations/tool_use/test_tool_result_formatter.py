"""Tests for :class:`ToolResultFormatter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.tool_use.tool_result_formatter import (
    ToolResultFormatter,
)
from pirn.domains.agents.types.tool_result import ToolResult
from pirn.tapestry import Tapestry


class TestToolResultFormatterHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_formats_successful_string_result(self) -> None:
        tool_result = ToolResult(call_id="c1", result="42 apples")
        with Tapestry() as t:
            ToolResultFormatter(
                tool_result=tool_result,
                _config=KnotConfig(id="fmt"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        formatted: str = result.outputs["fmt"]
        assert isinstance(formatted, str)
        assert "c1" in formatted
        assert "42 apples" in formatted

    async def test_formats_dict_result_as_json(self) -> None:
        tool_result = ToolResult(call_id="c2", result={"key": "value"})
        with Tapestry() as t:
            ToolResultFormatter(
                tool_result=tool_result,
                _config=KnotConfig(id="fmt"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        formatted: str = result.outputs["fmt"]
        assert "key" in formatted
        assert "value" in formatted

    async def test_formats_error_result(self) -> None:
        tool_result = ToolResult(call_id="c3", result=None, error="connection refused")
        with Tapestry() as t:
            ToolResultFormatter(
                tool_result=tool_result,
                _config=KnotConfig(id="fmt"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        formatted: str = result.outputs["fmt"]
        assert "c3" in formatted
        assert "connection refused" in formatted
        assert "failed" in formatted.lower()

    async def test_rejects_non_tool_result_at_construction(self) -> None:
        with self.assertRaisesRegex(TypeError, "tool_result"):
            with Tapestry():
                ToolResultFormatter(
                    tool_result="not-a-result",  # type: ignore[arg-type]
                    _config=KnotConfig(id="fmt"),
                )

    async def test_formats_list_result_as_json(self) -> None:
        tool_result = ToolResult(call_id="c4", result=[1, 2, 3])
        with Tapestry() as t:
            ToolResultFormatter(
                tool_result=tool_result,
                _config=KnotConfig(id="fmt"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        formatted: str = result.outputs["fmt"]
        assert "1" in formatted
        assert "2" in formatted
