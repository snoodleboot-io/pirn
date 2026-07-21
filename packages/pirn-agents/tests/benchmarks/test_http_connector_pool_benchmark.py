"""Pooled-vs-per-call connection-reuse micro-benchmark for :class:`HttpConnector` (F16-S1-T3).

Marked ``@pytest.mark.benchmark``. Like the other agents benchmarks it measures
wall-clock directly with :func:`time.perf_counter` and does not depend on the
pytest-benchmark plugin. A fake client whose *construction* costs a fixed latency
models an expensive connection/handshake, quantifying connection reuse — the
primary latency lever for tool-heavy agents:

* **per-call construction** — a fresh client (and thus a new connection) is built
  on every request, costing roughly ``N x latency``;
* **pooled reuse** — one :class:`HttpConnector` builds its client once and reuses
  it across all ``N`` requests, costing roughly ``1 x latency``.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import pytest

from pirn_agents.connectors.http_connector import HttpConnector


class _FakeResponse:
    def __init__(self) -> None:
        self.status_code = 200
        self.headers: dict[str, str] = {}

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        yield b"ok"


class _SlowToBuildClient:
    """Client whose construction costs a fixed latency (models a handshake)."""

    def __init__(self, latency: float) -> None:
        time.sleep(latency)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: object = None,
        params: object = None,
        extensions: object = None,
    ) -> _FakeResponse:
        return _FakeResponse()

    async def aclose(self) -> None:
        return None


def _resolver(_host: str) -> str:
    return "93.184.216.34"


@pytest.mark.benchmark
async def test_pooled_reuse_beats_per_call_connection() -> None:
    n = 20
    latency = 0.002

    # Per-call construction: a new client (new connection) on every request.
    start = time.perf_counter()
    for _ in range(n):
        connector = HttpConnector(client=_SlowToBuildClient(latency), resolver=_resolver)
        await connector.request("GET", "https://example.com/x")
    per_call_time = time.perf_counter() - start

    # Pooled reuse: build the client once, reuse across all requests.
    start = time.perf_counter()
    pooled = HttpConnector(client=_SlowToBuildClient(latency), resolver=_resolver)
    for _ in range(n):
        await pooled.request("GET", "https://example.com/x")
    pooled_time = time.perf_counter() - start

    assert pooled_time < per_call_time * 0.5
    speedup = per_call_time / pooled_time if pooled_time > 0 else float("inf")
    print(
        f"[benchmark] http_connector_pool N={n} latency={latency}s "
        f"per_call={per_call_time:.4f}s pooled={pooled_time:.4f}s speedup={speedup:.1f}x"
    )
