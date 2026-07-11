"""Tests for :class:`pirn_agents.mcp.mcp_toolset.McpToolset` (S2 / PIR-180, PIR-186).

Discovery populates an F1 :class:`Toolset`; the provider-neutral schema and the
tool result round-trip through F1's protocol — the toolset's ``schema()`` and a
``ToolCall`` dispatched through :class:`ParallelToolExecutor` into a
:class:`ToolResult`.
"""

from __future__ import annotations

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_toolset import McpToolset
from pirn_agents.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus
from tests.mcp.stub_mcp import StubMcpTransport


async def _discover() -> Toolset:
    client = McpClient(StubMcpTransport())
    await client.open()
    return await McpToolset(client=client).discover()


async def test_discover_builds_toolset_skipping_nameless() -> None:
    toolset = await _discover()

    assert isinstance(toolset, Toolset)
    names = [tool.name for tool in toolset]
    assert names == ["echo", "add", "boom"]  # the nameless descriptor is dropped


async def test_schema_is_provider_neutral_round_trip() -> None:
    toolset = await _discover()

    schema = toolset.schema()

    echo = next(entry for entry in schema if entry["name"] == "echo")
    assert echo == {
        "name": "echo",
        "description": "Echo the given text back.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    }


def _make_executor() -> ParallelToolExecutor:
    with Tapestry():
        return ParallelToolExecutor(
            tool_calls=[],
            toolset=Toolset(),
            _config=KnotConfig(id="pte", validate_io=False),
        )


async def test_result_round_trips_through_parallel_executor() -> None:
    toolset = await _discover()
    calls = [ToolCall(tool_name="echo", arguments={"text": "hello"}, call_id="c-1")]

    results = await _make_executor().process(
        tool_calls=calls, toolset=toolset, max_concurrency=4, timeout=None, retries=0
    )

    assert len(results) == 1
    assert results[0].call_id == "c-1"
    assert results[0].status is ToolStatus.OK
    assert results[0].result == "hello"


async def test_error_tool_round_trips_to_error_result() -> None:
    toolset = await _discover()
    calls = [ToolCall(tool_name="boom", arguments={}, call_id="c-err")]

    results = await _make_executor().process(
        tool_calls=calls, toolset=toolset, max_concurrency=1, timeout=None, retries=0
    )

    assert results[0].status is ToolStatus.ERROR


async def test_refresh_rediscovers() -> None:
    client = McpClient(StubMcpTransport())
    await client.open()
    toolset = McpToolset(client=client)

    first = await toolset.discover()
    second = await toolset.refresh()

    assert [t.name for t in first] == [t.name for t in second]
