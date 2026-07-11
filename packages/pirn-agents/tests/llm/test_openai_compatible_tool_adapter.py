"""Tests for :class:`OpenAICompatibleToolAdapter` via :class:`ToolCallCodec`."""

from __future__ import annotations

import json
import unittest

from pirn_agents.llm.openai_compatible_tool_adapter import OpenAICompatibleToolAdapter
from pirn_agents.tool_call_codec import ToolCallCodec
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_result import ToolResult
from tests.specializations.conftest import StubTool


class TestOpenAICompatibleToolAdapter(unittest.TestCase):
    def test_tool_declaration_shape(self) -> None:
        codec = ToolCallCodec(OpenAICompatibleToolAdapter())
        native = codec.encode_tools(Toolset([StubTool(name="search", description="find")]))
        assert native == [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "find",
                    "parameters": {"type": "object", "properties": {"input": {"type": "string"}}},
                },
            }
        ]

    def test_decode_single_tool_call_with_json_string_arguments(self) -> None:
        codec = ToolCallCodec(OpenAICompatibleToolAdapter())
        message = {
            "role": "assistant",
            "tool_calls": [
                {"id": "c1", "function": {"name": "search", "arguments": json.dumps({"q": "cats"})}}
            ],
        }
        calls = codec.decode_calls(message)
        assert len(calls) == 1
        assert calls[0].call_id == "c1"
        assert calls[0].arguments == {"q": "cats"}

    def test_decode_parallel_calls_preserve_ids(self) -> None:
        codec = ToolCallCodec(OpenAICompatibleToolAdapter())
        message = {
            "tool_calls": [
                {"id": "a", "function": {"name": "search", "arguments": '{"q": "1"}'}},
                {"id": "b", "function": {"name": "lookup", "arguments": '{"q": "2"}'}},
            ]
        }
        calls = codec.decode_calls(message)
        assert [c.call_id for c in calls] == ["a", "b"]
        assert [c.tool_name for c in calls] == ["search", "lookup"]

    def test_decode_no_tool_calls_is_empty(self) -> None:
        codec = ToolCallCodec(OpenAICompatibleToolAdapter())
        assert codec.decode_calls({"role": "assistant", "content": "hi"}) == []

    def test_encode_result_message(self) -> None:
        codec = ToolCallCodec(OpenAICompatibleToolAdapter())
        native = codec.encode_results([ToolResult(call_id="c1", result={"ok": True})])
        assert native == [{"role": "tool", "tool_call_id": "c1", "content": {"ok": True}}]


if __name__ == "__main__":
    unittest.main()
