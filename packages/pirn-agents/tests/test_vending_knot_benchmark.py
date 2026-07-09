"""Reuse-vs-per-call micro-benchmark for the vending-knot pattern.

Marked ``@pytest.mark.benchmark`` (marker registered in ``pyproject.toml``). It
deliberately does **not** depend on the pytest-benchmark plugin: wall-clock is
measured directly with :func:`time.perf_counter`. A stub tool-client whose
constructor sleeps a fixed tiny latency models an expensive client build. Two
strategies are compared over ``N`` iterations:

* **per-call construction** — a fresh client is built on every iteration, so the
  cost is roughly ``N x latency``.
* **vending (pooled) reuse** — the client is built once and reused across all
  ``N`` iterations via :class:`ToolClientKnot`, so the cost is roughly
  ``1 x latency``.

The assertion bound is loose so the test proves reuse clearly beats per-call
construction without being flaky on a busy CI host. Measured figures are printed
so an F10-style report can harvest them later.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.tool_client_knot import ToolClientKnot


class SlowToolClient(ConnectorBase):
    """Tool-client connector whose construction costs a fixed latency."""

    def __init__(self, *, latency: float) -> None:
        super().__init__(credential=None)
        time.sleep(latency)

    async def _create_client(self) -> Any:
        return object()


@pytest.mark.benchmark
async def test_vending_reuse_beats_per_call_construction() -> None:
    n = 20
    latency = 0.002

    with Tapestry():
        knot = ToolClientKnot.__new__(ToolClientKnot)
        object.__setattr__(knot, "_config", KnotConfig(id="tck-bench"))

    # Per-call construction: build a fresh client on every iteration.
    start = time.perf_counter()
    for _ in range(n):
        client = SlowToolClient(latency=latency)
        await knot.process(client=client)
    per_call_time = time.perf_counter() - start

    # Vending (pooled) reuse: build once, reuse across all iterations.
    start = time.perf_counter()
    pooled_client = SlowToolClient(latency=latency)
    for _ in range(n):
        await knot.process(client=pooled_client)
    pooled_time = time.perf_counter() - start

    # Loose, non-flaky bound: pooled reuse must clearly beat per-call builds.
    assert pooled_time < per_call_time * 0.5

    delta = per_call_time - pooled_time
    speedup = per_call_time / pooled_time if pooled_time > 0 else float("inf")
    print(
        f"[benchmark] vending-knot N={n} latency={latency}s "
        f"per_call={per_call_time:.4f}s pooled={pooled_time:.4f}s "
        f"delta={delta:.4f}s speedup={speedup:.1f}x"
    )
