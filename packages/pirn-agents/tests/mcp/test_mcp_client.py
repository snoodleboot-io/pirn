"""Tests for :class:`pirn_agents.mcp.mcp_client.McpClient` (S1 / PIR-149).

Lifecycle (handshake, capability negotiation, idempotent close), JSON-RPC
request/response correlation (including skipping interleaved notifications),
keep-alive ping, and error mapping — all driven by the in-memory
:class:`StubMcpTransport` (no real server).
"""

from __future__ import annotations

import pytest

from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.mcp.mcp_transport import McpTransport
from tests.mcp.stub_mcp import StubMcpTransport


async def test_open_performs_handshake_and_negotiates_capabilities() -> None:
    transport = StubMcpTransport()
    client = McpClient(transport)

    await client.open()

    assert client.is_open is True
    assert client.server_capabilities == {"tools": {}, "resources": {}, "prompts": {}}
    assert client.server_info == {"name": "stub-server", "version": "1.0"}
    # initialize request then the initialized notification were both sent.
    assert transport.sent[0]["method"] == "initialize"
    assert transport.sent[0]["params"]["clientInfo"]["name"] == "pirn-agents"
    assert transport.sent[1]["method"] == "notifications/initialized"
    assert "id" not in transport.sent[1]


async def test_open_is_idempotent() -> None:
    transport = StubMcpTransport()
    client = McpClient(transport)

    await client.open()
    await client.open()

    assert transport.opens == 1
    assert sum(1 for m in transport.sent if m.get("method") == "initialize") == 1


async def test_aclose_resets_state_and_is_idempotent() -> None:
    transport = StubMcpTransport()
    client = McpClient(transport)
    await client.open()

    await client.aclose()
    await client.aclose()

    assert client.is_open is False
    assert transport.closes == 2


async def test_request_ids_are_monotonic() -> None:
    transport = StubMcpTransport()
    client = McpClient(transport)
    await client.open()

    await client.list_tools()
    await client.list_tools()

    ids = [m["id"] for m in transport.sent if "id" in m]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


async def test_request_skips_interleaved_notification() -> None:
    transport = StubMcpTransport(notify_before_response=True)
    client = McpClient(transport)

    # The handshake itself already exercised a skipped notification.
    await client.open()
    tools = await client.list_tools()

    assert any(tool["name"] == "echo" for tool in tools)


async def test_ping_round_trips() -> None:
    transport = StubMcpTransport()
    client = McpClient(transport)
    await client.open()

    await client.ping()

    assert transport.sent[-1]["method"] == "ping"


async def test_server_error_is_mapped_to_mcp_error() -> None:
    def failing_initialize(_params: object) -> dict[str, object]:
        return {"__error__": {"code": -32000, "message": "nope", "data": {"why": "test"}}}

    transport = StubMcpTransport(handlers={"initialize": failing_initialize})
    client = McpClient(transport)

    with pytest.raises(McpError) as ctx:
        await client.open()

    assert ctx.value.code == -32000
    assert ctx.value.data == {"why": "test"}


async def test_call_tool_validates_arguments() -> None:
    transport = StubMcpTransport()
    client = McpClient(transport)
    await client.open()

    with pytest.raises(TypeError):
        await client.call_tool("echo", "not-a-mapping")  # type: ignore[arg-type]


async def test_constructor_rejects_non_transport() -> None:
    with pytest.raises(TypeError):
        McpClient("not-a-transport")  # type: ignore[arg-type]


async def test_is_open_false_when_transport_closed_after_open() -> None:
    transport = StubMcpTransport()
    client = McpClient(transport)
    await client.open()

    await transport.close()

    assert client.is_open is False


def test_transport_base_methods_raise_not_implemented() -> None:
    base = McpTransport()
    with pytest.raises(NotImplementedError):
        _ = base.is_open
