"""Tests for :class:`pirn_agents.mcp.mcp_resource_adapter.McpResourceAdapter`.

S3 / PIR-156, PIR-191, PIR-196: resource discovery/fetch, context-message
injection, memory-store injection (via ``StubMemoryStore``), and malformed-
resource handling.
"""

from __future__ import annotations

import pytest

from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.mcp.mcp_resource_adapter import McpResourceAdapter
from pirn_agents.types.agent_message import AgentMessage
from tests.conftest import StubMemoryStore
from tests.mcp.stub_mcp import StubMcpTransport


async def _adapter() -> McpResourceAdapter:
    client = McpClient(StubMcpTransport())
    await client.open()
    return McpResourceAdapter(client=client)


async def test_list_resources_surfaces_descriptors() -> None:
    adapter = await _adapter()

    resources = await adapter.list_resources()

    assert [r["uri"] for r in resources] == ["file:///a.txt", "file:///b.txt"]


async def test_read_text_returns_joined_content() -> None:
    adapter = await _adapter()

    text = await adapter.read_text("file:///a.txt")

    assert text == "content of file:///a.txt"


async def test_as_context_messages_discovers_all() -> None:
    adapter = await _adapter()

    messages = await adapter.as_context_messages()

    assert all(isinstance(m, AgentMessage) for m in messages)
    assert [m.role for m in messages] == ["system", "system"]
    assert messages[0].content == "content of file:///a.txt"
    assert messages[0].name == "file:///a.txt"


async def test_as_context_messages_honours_explicit_uris_and_role() -> None:
    adapter = await _adapter()

    messages = await adapter.as_context_messages(uris=["file:///b.txt"], role="user")

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "content of file:///b.txt"


async def test_inject_into_store_writes_each_resource() -> None:
    adapter = await _adapter()
    store = StubMemoryStore()

    keys = await adapter.inject_into_store(store, uris=["file:///a.txt"])

    assert keys == ["mcp:resource:file:///a.txt"]
    stored = await store.retrieve("mcp:resource:file:///a.txt")
    assert stored == {"uri": "file:///a.txt", "content": "content of file:///a.txt"}


async def test_malformed_resource_raises() -> None:
    adapter = await _adapter()

    with pytest.raises(McpError):
        await adapter.read_text("file:///malformed")


async def test_constructor_rejects_non_client() -> None:
    with pytest.raises(TypeError):
        McpResourceAdapter(client=object())  # type: ignore[arg-type]


async def test_inject_rejects_non_store() -> None:
    adapter = await _adapter()
    with pytest.raises(TypeError):
        await adapter.inject_into_store(object())  # type: ignore[arg-type]
