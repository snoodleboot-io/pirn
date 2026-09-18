"""Tests for :class:`pirn_agents.mcp.mcp_connector.McpConnector` (S5 / PIR-207, PIR-218).

Single-session vending (build once, reuse), reconnect with deterministic
core ``KnotRetryPolicy`` backoff driven by an injected ``sleep``, reconnect
exhaustion, and partial-open cleanup — all with the in-memory stub transport.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from pirn.core.knot_retry_policy import KnotRetryPolicy

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
        reconnect=KnotRetryPolicy(max_attempts=5, base_delay=0.1, max_delay=10.0, jitter=False),
        sleep=sleep,
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
        reconnect=KnotRetryPolicy(max_attempts=6, base_delay=1.0, max_delay=1.5, jitter=False),
        sleep=sleep,
    )

    await connector.session()

    assert sleeps == [1.0, 1.5, 1.5]  # 1, 2->cap 1.5, 4->cap 1.5


async def test_reconnect_exhaustion_raises_mcp_error() -> None:
    factory = FlakyFactory(fail_first=10)
    sleeps, sleep = _recording_sleep()
    connector = McpConnector(
        transport_factory=factory,
        reconnect=KnotRetryPolicy(max_attempts=3, base_delay=0.01, jitter=False),
        sleep=sleep,
    )

    with pytest.raises(McpError):
        await connector.session()

    assert factory.calls == 3
    assert len(sleeps) == 2  # no sleep after the final failed attempt


async def test_failed_open_closes_partial_transport() -> None:
    factory = FlakyFactory(fail_first=1)
    _sleeps, sleep = _recording_sleep()
    connector = McpConnector(transport_factory=factory, rng=lambda: 0.0, sleep=sleep)

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
        McpConnector(transport_factory=object())


def test_rejects_a_reconnect_that_is_not_a_policy() -> None:
    with pytest.raises(TypeError, match="KnotRetryPolicy"):
        McpConnector(transport_factory=StubMcpTransport, reconnect=5)


async def test_jitter_draw_scales_the_delay() -> None:
    factory = FlakyFactory(fail_first=1)
    sleeps, sleep = _recording_sleep()
    connector = McpConnector(
        transport_factory=factory,
        reconnect=KnotRetryPolicy(max_attempts=2, base_delay=0.4),
        rng=lambda: 0.5,
        sleep=sleep,
    )

    await connector.session()

    assert sleeps == [0.2]
