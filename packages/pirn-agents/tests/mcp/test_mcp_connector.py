"""Tests for :class:`pirn_agents.mcp.mcp_connector.McpConnector` (S5 / PIR-207, PIR-218).

Single-session vending (build once, reuse), reconnect with deterministic
exponential+jitter backoff driven by an injected ``sleep``/``jitter``, reconnect
exhaustion, and partial-open cleanup — all with the in-memory stub transport.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest

from pirn_agents.mcp.mcp_connector import McpConnector
from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.mcp.mcp_transport import McpTransport
from tests.mcp.stub_mcp import StubMcpTransport


class FlakyFactory:
    """Transport factory whose first ``fail_first`` opens fail (shared count)."""

    def __init__(self, *, fail_first: int = 0) -> None:
        self._fail_first = fail_first
        self.calls = 0
        self.transports: list[StubMcpTransport] = []

    def __call__(self) -> McpTransport:
        self.calls += 1
        fail = 1 if self.calls <= self._fail_first else 0
        transport = StubMcpTransport(fail_opens=fail)
        self.transports.append(transport)
        return transport


def _recording_sleep() -> tuple[list[float], Callable[[float], Awaitable[None]]]:
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    return sleeps, sleep


async def test_session_built_once_and_reused() -> None:
    factory = FlakyFactory()
    connector = McpConnector(transport_factory=factory)

    first = await connector.session()
    second = await connector.session()

    assert first is second
    assert first.is_open is True
    assert factory.calls == 1


async def test_reconnect_uses_exponential_backoff_schedule() -> None:
    factory = FlakyFactory(fail_first=2)
    sleeps, sleep = _recording_sleep()
    connector = McpConnector(
        transport_factory=factory,
        backoff_base=0.1,
        backoff_cap=10.0,
        jitter=lambda: 0.0,
        sleep=sleep,
        max_reconnect_attempts=5,
    )

    client = await connector.session()

    assert client.is_open is True
    assert factory.calls == 3  # two failures, then success
    assert sleeps == [0.1, 0.2]  # base*2^0, base*2^1


async def test_backoff_is_capped() -> None:
    factory = FlakyFactory(fail_first=3)
    sleeps, sleep = _recording_sleep()
    connector = McpConnector(
        transport_factory=factory,
        backoff_base=1.0,
        backoff_cap=1.5,
        jitter=lambda: 0.0,
        sleep=sleep,
        max_reconnect_attempts=6,
    )

    await connector.session()

    assert sleeps == [1.0, 1.5, 1.5]  # 1, 2->cap 1.5, 4->cap 1.5


async def test_reconnect_exhaustion_raises_mcp_error() -> None:
    factory = FlakyFactory(fail_first=10)
    sleeps, sleep = _recording_sleep()
    connector = McpConnector(
        transport_factory=factory,
        backoff_base=0.01,
        jitter=lambda: 0.0,
        sleep=sleep,
        max_reconnect_attempts=3,
    )

    with pytest.raises(McpError):
        await connector.session()

    assert factory.calls == 3
    assert len(sleeps) == 2  # no sleep after the final failed attempt


async def test_failed_open_closes_partial_transport() -> None:
    factory = FlakyFactory(fail_first=1)
    _sleeps, sleep = _recording_sleep()
    connector = McpConnector(transport_factory=factory, jitter=lambda: 0.0, sleep=sleep)

    await connector.session()

    # The first (failed) transport was closed during cleanup.
    assert factory.transports[0].closes >= 1


async def test_close_tears_down_session() -> None:
    factory = FlakyFactory()
    connector = McpConnector(transport_factory=factory)
    client = await connector.session()

    await connector.close()

    assert client.is_open is False


def test_rejects_non_callable_factory() -> None:
    with pytest.raises(TypeError):
        McpConnector(transport_factory=object())  # type: ignore[arg-type]


def test_rejects_zero_attempts() -> None:
    with pytest.raises(ValueError):
        McpConnector(transport_factory=StubMcpTransport, max_reconnect_attempts=0)
