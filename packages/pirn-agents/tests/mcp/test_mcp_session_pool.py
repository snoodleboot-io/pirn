"""Tests for :class:`pirn_agents.mcp.mcp_session_pool.McpSessionPool` (S5 / PIR-207).

The pool vends one connector per server key, constructed once, and closes them
all on teardown.
"""

from __future__ import annotations

import pytest

from pirn_agents.mcp.mcp_connector import McpConnector
from pirn_agents.mcp.mcp_session_pool import McpSessionPool
from tests.mcp.stub_mcp import StubMcpTransport


def _connector_factory() -> tuple[list[int], object]:
    builds = [0]

    def factory() -> McpConnector:
        builds[0] += 1
        return McpConnector(transport_factory=StubMcpTransport)

    return builds, factory


async def test_connector_built_once_per_key() -> None:
    builds, factory = _connector_factory()
    pool = McpSessionPool(factories={"srv": factory})

    first = pool.acquire_connector("srv")
    second = pool.acquire_connector("srv")

    assert first is second
    assert builds[0] == 1


async def test_session_vends_live_client_via_pool() -> None:
    _builds, factory = _connector_factory()
    pool = McpSessionPool()
    pool.register("srv", factory)

    client = await pool.session("srv")

    assert client.is_open is True
    # A second vend reuses the same connector's single session.
    assert await pool.session("srv") is client


async def test_distinct_keys_get_distinct_connectors() -> None:
    _b1, f1 = _connector_factory()
    _b2, f2 = _connector_factory()
    pool = McpSessionPool(factories={"a": f1, "b": f2})

    assert pool.acquire_connector("a") is not pool.acquire_connector("b")


async def test_unknown_key_raises_key_error() -> None:
    pool = McpSessionPool()
    with pytest.raises(KeyError):
        pool.acquire_connector("missing")


async def test_close_tears_down_all_sessions() -> None:
    _builds, factory = _connector_factory()
    pool = McpSessionPool(factories={"srv": factory})
    client = await pool.session("srv")

    await pool.close()

    assert client.is_open is False
    # After close the connector is forgotten and rebuilt on next acquire.
    assert pool.acquire_connector("srv") is not None


def test_register_rejects_bad_arguments() -> None:
    pool = McpSessionPool()
    with pytest.raises(TypeError):
        pool.register("", lambda: McpConnector(transport_factory=StubMcpTransport))
    with pytest.raises(TypeError):
        pool.register("srv", object())  # type: ignore[arg-type]
