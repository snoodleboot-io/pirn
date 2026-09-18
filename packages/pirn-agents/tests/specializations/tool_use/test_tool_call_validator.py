"""Tests for :class:`ToolCallValidator`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.tool_use.tool_call_validator import (
    ToolCallValidator,
)
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory
from tests.specializations.conftest import StubTool

#: A schema-declared tool requiring a string 'query' field, no Python
#: signature to introspect (mirrors a strict, externally-declared schema).
StrictSchemaTool = ToolFactory.schema_declared_class(
    "StrictSchemaTool",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    lambda **kwargs: kwargs,
    description="tool with strict schema",
    tool_name="strict_tool",
)


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
                tools=[StrictSchemaTool],
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
                tools=[StrictSchemaTool],
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
                tools=[StrictSchemaTool],
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
                tools=[StrictSchemaTool],
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
                    tools=["bad"],
                    _config=KnotConfig(id="val"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_tool_in_tools_list(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        with Tapestry():
            k = ToolCallValidator.__new__(ToolCallValidator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(tool_call=call, tools=["not-a-tool"])

    async def test_process_rejects_non_tool_call(self) -> None:
        valid_call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        with Tapestry():
            k = ToolCallValidator(
                tool_call=valid_call, tools=[StubTool(name="t")], _config=KnotConfig(id="x")
            )
        result = await k({"tool_call": "not-a-call", "tools": [StubTool(name="t")]})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"
