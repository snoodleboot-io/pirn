"""Tests for :class:`ToolCallValidator`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.tool_use.tool_call_validator import (
    ToolCallValidator,
)
from pirn_agents.tool import Tool
from pirn_agents.types.tool_call import ToolCall
from pirn.tapestry import Tapestry

from tests.specializations.conftest import StubTool


class StrictSchemaTool(Tool):
    """Tool with a strict schema requiring a string 'query' field."""

    @property
    def name(self) -> str:
        return "strict_tool"

    @property
    def description(self) -> str:
        return "tool with strict schema"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        return arguments


class TestToolCallValidatorHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_passes_valid_tool_call_through(self) -> None:
        call = ToolCall(
            tool_name="strict_tool",
            arguments={"query": "find me stuff"},
            call_id="c1",
        )
        with Tapestry() as t:
            ToolCallValidator(
                tool_call=call,
                tools=[StrictSchemaTool()],
                _config=KnotConfig(id="val"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        validated = result.outputs["val"]
        assert validated == call


class TestToolCallValidatorRejections(unittest.IsolatedAsyncioTestCase):
    async def test_raises_on_missing_required_field(self) -> None:
        call = ToolCall(
            tool_name="strict_tool",
            arguments={"limit": 5},
            call_id="c1",
        )
        with Tapestry() as t:
            ToolCallValidator(
                tool_call=call,
                tools=[StrictSchemaTool()],
                _config=KnotConfig(id="val"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_raises_on_wrong_type(self) -> None:
        call = ToolCall(
            tool_name="strict_tool",
            arguments={"query": 123},
            call_id="c1",
        )
        with Tapestry() as t:
            ToolCallValidator(
                tool_call=call,
                tools=[StrictSchemaTool()],
                _config=KnotConfig(id="val"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_raises_on_unknown_tool(self) -> None:
        call = ToolCall(
            tool_name="ghost_tool",
            arguments={},
            call_id="c1",
        )
        with Tapestry() as t:
            ToolCallValidator(
                tool_call=call,
                tools=[StubTool(name="other")],
                _config=KnotConfig(id="val"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_raises_on_extra_field_when_additional_properties_false(self) -> None:
        call = ToolCall(
            tool_name="strict_tool",
            arguments={"query": "ok", "unexpected": "value"},
            call_id="c1",
        )
        with Tapestry() as t:
            ToolCallValidator(
                tool_call=call,
                tools=[StrictSchemaTool()],
                _config=KnotConfig(id="val"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_non_tool_in_list(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        with self.assertRaises(TypeError):
            with Tapestry():
                ToolCallValidator(
                    tool_call=call,
                    tools=["bad"],  # type: ignore[list-item]
                    _config=KnotConfig(id="val"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_tool_in_tools_list(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        with Tapestry():
            k = ToolCallValidator.__new__(ToolCallValidator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(tool_call=call, tools=["not-a-tool"])  # type: ignore[list-item]

    async def test_process_rejects_non_tool_call(self) -> None:
        with Tapestry():
            k = ToolCallValidator.__new__(ToolCallValidator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(tool_call="not-a-call", tools=[StubTool(name="t")])  # type: ignore[arg-type]
