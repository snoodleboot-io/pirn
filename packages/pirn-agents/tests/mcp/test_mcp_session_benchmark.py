"""Concurrent-``call_tool`` benchmark over a single vended MCP session (S5 / PIR-222).

Confirms that running many tool calls concurrently through F1's bounded
:class:`ParallelToolExecutor` incurs **no per-call session overhead**: one
connector builds exactly one client, the transport opens exactly once, and all
``N`` calls share that vended session. Wall-clock is measured directly (no
pytest-benchmark dependency) and printed for later harvest.
"""

from __future__ import annotations

import time

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.mcp.mcp_connector import McpConnector
from pirn_agents.mcp.mcp_toolset import McpToolset
from pirn_agents.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus
from tests.mcp.stub_mcp import StubMcpTransport


class CountingFactory:
    """Transport factory that records how many transports it built."""

    def __init__(self) -> None:
        self.calls = 0
        self.transports: list[StubMcpTransport] = []

    def __call__(self) -> StubMcpTransport:
        self.calls += 1
        transport = StubMcpTransport()
        self.transports.append(transport)
        return transport


def _make_executor() -> ParallelToolExecutor:
    with Tapestry():
        return ParallelToolExecutor(
            tool_calls=[],
            toolset=Toolset(),
            _config=KnotConfig(id="pte", validate_io=False),
        )


@pytest.mark.benchmark
async def test_concurrent_call_tool_reuses_single_vended_session() -> None:
    factory = CountingFactory()
    connector = McpConnector(transport_factory=factory)

    # One vended session backs discovery and every subsequent call.
    session = await connector.session()
    toolset = await McpToolset(client=session).discover()

    n = 32
    calls = [
        ToolCall(tool_name="echo", arguments={"text": f"msg-{i}"}, call_id=f"c-{i}")
        for i in range(n)
    ]

    start = time.perf_counter()
    results = await _make_executor().process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )
    elapsed = time.perf_counter() - start

    assert len(results) == n
    assert all(r.status is ToolStatus.OK for r in results)
    assert results[0].result == "msg-0"

    # The core assertion: exactly one session was built/opened for all N calls —
    # no per-call reconnect overhead.
    assert factory.calls == 1
    assert factory.transports[0].opens == 1
    assert connector._client is session

    print(
        f"[benchmark] mcp concurrent call_tool N={n} max_concurrency=8 "
        f"elapsed={elapsed:.4f}s session_builds={factory.calls} "
        f"transport_opens={factory.transports[0].opens}"
    )
