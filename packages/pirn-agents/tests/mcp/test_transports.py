"""Tests for the concrete MCP transports (S1 / PIR-149).

The real ``mcp`` backend is not installed in the default suite, so these tests
prove the lazy-import contract (importing the module is backend-free; opening a
transport raises the friendly ``[mcp]`` install error) plus constructor
validation. No subprocess or socket is ever spawned.
"""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from pirn_agents.mcp.stdio_transport import StdioTransport
from pirn_agents.mcp.streamable_http_transport import StreamableHttpTransport


async def test_stdio_open_raises_friendly_error_without_backend() -> None:
    # mcp may be installed (CI installs the [mcp] extra); force it absent so the
    # friendly install-error path is exercised deterministically.
    transport = StdioTransport(command="python", args=["-m", "server"])
    with mock.patch.dict(sys.modules, {"mcp": None}):
        with pytest.raises(ImportError) as ctx:
            await transport.open()
    assert 'pip install "pirn-agents[mcp]"' in str(ctx.value)
    assert transport.is_open is False


async def test_streamable_http_open_raises_friendly_error_without_backend() -> None:
    transport = StreamableHttpTransport(url="https://example.test/mcp")
    with mock.patch.dict(sys.modules, {"mcp": None}):
        with pytest.raises(ImportError) as ctx:
            await transport.open()
    assert 'pip install "pirn-agents[mcp]"' in str(ctx.value)
    assert transport.is_open is False


def test_stdio_rejects_empty_command() -> None:
    with pytest.raises(TypeError):
        StdioTransport(command="")


def test_streamable_http_rejects_empty_url() -> None:
    with pytest.raises(TypeError):
        StreamableHttpTransport(url="")


async def test_send_before_open_raises_runtime_error() -> None:
    transport = StdioTransport(command="python")
    with pytest.raises(RuntimeError):
        await transport.send({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}})


async def test_close_is_idempotent_before_open() -> None:
    transport = StreamableHttpTransport(url="https://example.test/mcp")
    await transport.close()
    await transport.close()
    assert transport.is_open is False
