"""Tests for :class:`pirn_agents.mcp.mcp_tool.McpTool` (S2 / PIR-153, PIR-178).

Proves the descriptor→``Tool`` mapping (name/description/parameters_schema), the
``invoke``→``tools/call`` raw-value path, structured-content handling, and the
``as_tool_result`` path that wraps into an F1 :class:`ToolResult` — including a
server-reported error becoming a ``ToolStatus.ERROR`` result.
"""

from __future__ import annotations

import pytest

from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.mcp.mcp_tool import McpTool
from pirn_agents.tool import Tool
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus
from tests.mcp.stub_mcp import StubMcpTransport


async def _echo_tool() -> McpTool:
    client = McpClient(StubMcpTransport())
    await client.open()
    descriptors = await client.list_tools()
    echo = next(d for d in descriptors if d["name"] == "echo")
    return McpTool.from_descriptor(client=client, descriptor=echo)


async def test_descriptor_maps_name_description_and_schema() -> None:
    tool = await _echo_tool()

    assert isinstance(tool, Tool)
    assert tool.name == "echo"
    assert tool.description == "Echo the given text back."
    assert tool.parameters_schema["properties"] == {"text": {"type": "string"}}


async def test_invoke_returns_mapped_text_result() -> None:
    tool = await _echo_tool()

    result = await tool.invoke({"text": "hi there"})

    assert result == "hi there"


async def test_invoke_returns_structured_content() -> None:
    client = McpClient(StubMcpTransport())
    await client.open()
    descriptors = await client.list_tools()
    add = next(d for d in descriptors if d["name"] == "add")
    tool = McpTool.from_descriptor(client=client, descriptor=add)

    result = await tool.invoke({"a": 2, "b": 3})

    assert result == {"sum": 5}


async def test_invoke_raises_on_server_error_flag() -> None:
    client = McpClient(StubMcpTransport())
    await client.open()
    tool = McpTool(client=client, name="boom")

    with pytest.raises(McpError):
        await tool.invoke({})


async def test_as_tool_result_ok_round_trips_call_id() -> None:
    tool = await _echo_tool()
    call = ToolCall(tool_name="echo", arguments={"text": "roundtrip"}, call_id="c-1")

    result = await tool.as_tool_result(call)

    assert result.call_id == "c-1"
    assert result.status is ToolStatus.OK
    assert result.result == "roundtrip"
    assert result.error is None


async def test_as_tool_result_maps_server_error_to_error_status() -> None:
    client = McpClient(StubMcpTransport())
    await client.open()
    tool = McpTool(client=client, name="boom")
    call = ToolCall(tool_name="boom", arguments={}, call_id="c-2")

    result = await tool.as_tool_result(call)

    assert result.status is ToolStatus.ERROR
    assert result.call_id == "c-2"
    assert result.error is not None
    assert "kaboom" in result.error


async def test_invoke_rejects_non_mapping_arguments() -> None:
    tool = await _echo_tool()
    with pytest.raises(TypeError):
        await tool.invoke("nope")  # type: ignore[arg-type]


async def test_constructor_rejects_non_client() -> None:
    with pytest.raises(TypeError):
        McpTool(client="nope", name="echo")  # type: ignore[arg-type]


async def test_default_schema_when_missing() -> None:
    client = McpClient(StubMcpTransport())
    await client.open()
    tool = McpTool(client=client, name="echo")
    assert tool.parameters_schema == {"type": "object", "properties": {}}
