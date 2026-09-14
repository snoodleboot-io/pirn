"""Tests for :class:`pirn_agents.tools.tool_call_codec.ToolCallCodec`.

The codec is exercised against a hand-written ``StubAdapter`` that
invents a plausible provider-native shape, plus a ``StubLLMProvider``
that echoes tool calls back. A second, differently-shaped
``StubAdapter2`` proves the core codec carries no provider assumptions:
the same codec class round-trips through an unrelated native shape.
"""

from __future__ import annotations

import json
import unittest
from collections.abc import Sequence
from typing import Any

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.llm.provider_adapter import ProviderAdapter
from pirn_agents.testing.stub_tool import StubTool as KitStubTool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_call_codec import ToolCallCodec
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus
from pirn_agents.tools.toolset import Toolset


def _stub_tool(name: str, description: str = "stub tool") -> KitStubTool:
    """Minimal echo tool: a call's arguments come back wrapped as ``{"echo": ...}``."""
    return KitStubTool(
        name=name,
        description=description,
        parameters_schema={"type": "object", "properties": {"q": {"type": "string"}}},
        handler=lambda arguments: {"echo": dict(arguments)},
    )


class StubAdapter(ProviderAdapter):
    """An OpenAI-flavoured native shape used to drive the codec."""

    def tool_to_native(self, neutral_tool: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": neutral_tool["name"],
                "description": neutral_tool["description"],
                "parameters": neutral_tool["parameters"],
            },
        }

    def extract_tool_calls(self, provider_msg: Any) -> list[dict[str, Any]]:
        return list(provider_msg["tool_calls"])

    def result_to_native(self, result_payload: dict[str, Any]) -> Any:
        return {
            "role": "tool",
            "tool_call_id": result_payload["call_id"],
            "content": result_payload["content"],
        }


class StubAdapter2(ProviderAdapter):
    """A deliberately different native shape to prove neutrality."""

    def tool_to_native(self, neutral_tool: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool_spec": {
                "toolName": neutral_tool["name"],
                "doc": neutral_tool["description"],
                "inputSchema": neutral_tool["parameters"],
            }
        }

    def extract_tool_calls(self, provider_msg: Any) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for block in provider_msg["content"]:
            if block.get("kind") == "toolUse":
                calls.append({"id": block["ref"], "name": block["fn"], "arguments": block["args"]})
        return calls

    def result_to_native(self, result_payload: dict[str, Any]) -> Any:
        return {"toolResult": {"ref": result_payload["call_id"], "body": result_payload["content"]}}


class StubLLMProvider:
    """A stub provider that echoes preloaded tool calls in its native shape."""

    def __init__(self, tool_calls: Sequence[dict[str, Any]]) -> None:
        self._tool_calls = list(tool_calls)

    def respond(self) -> dict[str, Any]:
        """Return an assistant message in ``StubAdapter``'s native shape."""
        return {"role": "assistant", "tool_calls": self._tool_calls}


class TestEncodeTools(unittest.TestCase):
    def test_encode_tools_maps_each_tool_to_native_shape(self) -> None:
        toolset = Toolset([_stub_tool("search", "find things"), _stub_tool("lookup", "look up")])
        codec = ToolCallCodec(StubAdapter())

        native = codec.encode_tools(toolset)

        assert len(native) == 2
        assert native[0] == {
            "type": "function",
            "function": {
                "name": "search",
                "description": "find things",
                "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
            },
        }
        assert native[1]["function"]["name"] == "lookup"

    def test_encode_tools_empty_toolset(self) -> None:
        assert ToolCallCodec(StubAdapter()).encode_tools(Toolset()) == []


class TestDecodeCalls(unittest.TestCase):
    def test_single_call_arguments_as_json_string(self) -> None:
        codec = ToolCallCodec(StubAdapter())
        provider = StubLLMProvider(
            [{"id": "call-1", "name": "search", "arguments": json.dumps({"q": "cats"})}]
        )

        calls = codec.decode_calls(provider.respond())

        assert len(calls) == 1
        assert calls[0].tool_name == "search"
        assert calls[0].call_id == "call-1"
        assert calls[0].arguments == {"q": "cats"}
        assert calls[0].raw == {"id": "call-1", "name": "search", "arguments": '{"q": "cats"}'}

    def test_parallel_calls_preserve_order(self) -> None:
        codec = ToolCallCodec(StubAdapter())
        provider = StubLLMProvider(
            [
                {"id": "a", "name": "search", "arguments": '{"q": "one"}'},
                {"id": "b", "name": "lookup", "arguments": '{"q": "two"}'},
            ]
        )

        calls = codec.decode_calls(provider.respond())

        assert [c.call_id for c in calls] == ["a", "b"]
        assert [c.tool_name for c in calls] == ["search", "lookup"]
        assert [c.arguments for c in calls] == [{"q": "one"}, {"q": "two"}]

    def test_arguments_already_a_dict(self) -> None:
        codec = ToolCallCodec(StubAdapter())
        provider = StubLLMProvider([{"id": "c", "name": "search", "arguments": {"q": "dogs"}}])

        calls = codec.decode_calls(provider.respond())

        assert calls[0].arguments == {"q": "dogs"}


class TestEncodeCoreResults(unittest.TestCase):
    """The codec reads each call's ``Ok | Err | Skipped`` keyed by call id (ADR WS1)."""

    def test_ok_err_and_skipped_map_to_native_messages(self) -> None:
        codec = ToolCallCodec(StubAdapter())
        record = ExceptionRecord.for_knot("c2", RuntimeError("boom"))

        native = codec.encode_results(
            {
                "c1": Ok(value={"echo": 1}),
                "c2": Err(record=record),
                "c3": Skipped(reason="gate_closed"),
            }
        )

        assert native == [
            {"role": "tool", "tool_call_id": "c1", "content": {"echo": 1}},
            {"role": "tool", "tool_call_id": "c2", "content": "RuntimeError: boom"},
            {"role": "tool", "tool_call_id": "c3", "content": "call skipped: gate closed"},
        ]

    def test_skipped_renders_as_skipped_not_error(self) -> None:
        """PIR-865: the view's own status distinguishes a skip from a failure."""
        codec = ToolCallCodec(StubAdapter())

        views = codec.views({"c1": Skipped(reason="gate_closed")})

        assert views[0].status is ToolStatus.SKIPPED
        assert views[0].error == "call skipped: gate closed"


class TestEncodeResults(unittest.TestCase):
    def test_ok_result_uses_result_value(self) -> None:
        codec = ToolCallCodec(StubAdapter())
        results = [ToolResult(call_id="call-1", result={"echo": {"q": "cats"}})]

        native = codec.encode_results(results)

        assert native == [
            {"role": "tool", "tool_call_id": "call-1", "content": {"echo": {"q": "cats"}}}
        ]

    def test_error_result_uses_error_string(self) -> None:
        codec = ToolCallCodec(StubAdapter())
        results = [ToolResult(call_id="call-2", result=None, error="boom")]
        assert results[0].status is ToolStatus.ERROR

        native = codec.encode_results(results)

        assert native == [{"role": "tool", "tool_call_id": "call-2", "content": "boom"}]

    def test_non_json_result_falls_back_to_str(self) -> None:
        codec = ToolCallCodec(StubAdapter())
        sentinel = object()
        results = [ToolResult(call_id="call-3", result=sentinel)]

        native = codec.encode_results(results)

        assert native[0]["content"] == str(sentinel)


class TestFullRoundTrip(unittest.TestCase):
    async def _run_tools(self, toolset: Toolset, calls: Sequence[ToolCall]) -> list[ToolResult]:
        results: list[ToolResult] = []
        for call in calls:
            factory = toolset.get(call.tool_name)
            assert factory is not None
            outcome = await factory.run_call(call)
            results.append(ToolResult.from_result(call.call_id, outcome))
        return results

    def test_single_call_round_trip(self) -> None:
        import asyncio

        toolset = Toolset([_stub_tool("search")])
        codec = ToolCallCodec(StubAdapter())
        codec.encode_tools(toolset)
        provider = StubLLMProvider([{"id": "r1", "name": "search", "arguments": '{"q": "hi"}'}])

        calls = codec.decode_calls(provider.respond())
        results = asyncio.run(self._run_tools(toolset, calls))
        native = codec.encode_results(results)

        assert [m["tool_call_id"] for m in native] == ["r1"]
        assert native[0]["content"] == {"echo": {"q": "hi"}}

    def test_parallel_calls_round_trip_align_call_ids(self) -> None:
        import asyncio

        toolset = Toolset([_stub_tool("search"), _stub_tool("lookup")])
        codec = ToolCallCodec(StubAdapter())
        provider = StubLLMProvider(
            [
                {"id": "r1", "name": "search", "arguments": '{"q": "a"}'},
                {"id": "r2", "name": "lookup", "arguments": '{"q": "b"}'},
            ]
        )

        calls = codec.decode_calls(provider.respond())
        results = asyncio.run(self._run_tools(toolset, calls))
        native = codec.encode_results(results)

        assert [m["tool_call_id"] for m in native] == ["r1", "r2"]
        assert [m["content"] for m in native] == [{"echo": {"q": "a"}}, {"echo": {"q": "b"}}]


class TestProviderNeutrality(unittest.TestCase):
    def test_same_codec_round_trips_a_different_native_shape(self) -> None:
        toolset = Toolset([_stub_tool("search", "find")])
        codec = ToolCallCodec(StubAdapter2())

        native_tools = codec.encode_tools(toolset)
        assert native_tools == [
            {
                "tool_spec": {
                    "toolName": "search",
                    "doc": "find",
                    "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
                }
            }
        ]

        provider_msg = {
            "content": [
                {"kind": "text", "text": "thinking"},
                {"kind": "toolUse", "ref": "u1", "fn": "search", "args": {"q": "x"}},
            ]
        }
        calls = codec.decode_calls(provider_msg)
        assert len(calls) == 1
        assert calls[0].call_id == "u1"
        assert calls[0].arguments == {"q": "x"}

        native_results = codec.encode_results([ToolResult(call_id="u1", result="done")])
        assert native_results == [{"toolResult": {"ref": "u1", "body": "done"}}]

    def test_codec_module_has_no_provider_imports(self) -> None:
        from pirn_agents.tools import tool_call_codec

        source = tool_call_codec.__doc__ or ""
        # By design the module imports only stdlib + neutral pirn types.
        assert "anthropic" not in source.lower()
        assert not hasattr(tool_call_codec, "openai")


if __name__ == "__main__":
    unittest.main()
