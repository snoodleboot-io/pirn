"""Tests for :class:`AnthropicMessagesToolAdapter` via :class:`ToolCallCodec`."""

from __future__ import annotations

import unittest

from pirn_agents.llm.anthropic_messages_tool_adapter import AnthropicMessagesToolAdapter
from pirn_agents.tool_call_codec import ToolCallCodec
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_result import ToolResult
from tests.specializations.conftest import StubTool


class TestAnthropicMessagesToolAdapter(unittest.TestCase):
    def test_tool_declaration_uses_input_schema(self) -> None:
        codec = ToolCallCodec(AnthropicMessagesToolAdapter())
        native = codec.encode_tools(Toolset([StubTool(name="search", description="find")]))
        assert native == [
            {
                "name": "search",
                "description": "find",
                "input_schema": {"type": "object", "properties": {"input": {"type": "string"}}},
            }
        ]

    def test_decode_tool_use_blocks_with_object_arguments(self) -> None:
        codec = ToolCallCodec(AnthropicMessagesToolAdapter())
        response = {
            "content": [
                {"type": "text", "text": "let me look"},
                {"type": "tool_use", "id": "tu1", "name": "search", "input": {"q": "cats"}},
            ]
        }
        calls = codec.decode_calls(response)
        assert len(calls) == 1
        assert calls[0].call_id == "tu1"
        assert calls[0].tool_name == "search"
        assert calls[0].arguments == {"q": "cats"}

    def test_decode_parallel_tool_use_blocks(self) -> None:
        codec = ToolCallCodec(AnthropicMessagesToolAdapter())
        response = {
            "content": [
                {"type": "tool_use", "id": "a", "name": "search", "input": {"q": "1"}},
                {"type": "tool_use", "id": "b", "name": "lookup", "input": {"q": "2"}},
            ]
        }
        calls = codec.decode_calls(response)
        assert [c.call_id for c in calls] == ["a", "b"]
        assert [c.tool_name for c in calls] == ["search", "lookup"]

    def test_decode_no_tool_use_is_empty(self) -> None:
        codec = ToolCallCodec(AnthropicMessagesToolAdapter())
        assert codec.decode_calls({"content": [{"type": "text", "text": "hi"}]}) == []

    def test_encode_result_is_user_tool_result_message(self) -> None:
        codec = ToolCallCodec(AnthropicMessagesToolAdapter())
        native = codec.encode_results([ToolResult(call_id="tu1", result="done")])
        assert native == [
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "tu1", "content": "done"}],
            }
        ]


if __name__ == "__main__":
    unittest.main()
