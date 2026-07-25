"""Micro-benchmark: in-memory ``GraphStore`` upsert/query throughput (S1-T3).

Guards against regressions in the adjacency-list reference impl by measuring
node/edge upsert and neighbor/query latency at increasing graph sizes. The
adjacency indices make neighborhood expansion O(degree), not O(edges), so the
loose bounds prove responsiveness without being flaky on a busy CI host.
Measured figures are printed for an F10-style report.
"""

from __future__ import annotations

import time

import pytest

from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.graph_stores.in_memory_graph_store import InMemoryGraphStore


@pytest.mark.benchmark
async def test_upsert_and_neighbor_throughput() -> None:
    n = 5_000
    store = InMemoryGraphStore()

    nodes = [GraphNode.create(id=str(i), type="N", properties={"i": i}) for i in range(n)]
    # A chain plus a hub: node 0 is adjacent to the first 100 nodes so the
    # neighborhood query has real fan-out to expand.
    edges = [
        GraphEdge.create(source_id=str(i), target_id=str(i + 1), type="NEXT") for i in range(n - 1)
    ]
    edges += [GraphEdge.create(source_id="0", target_id=str(i), type="HUB") for i in range(1, 101)]

    start = time.perf_counter()
    await store.upsert_nodes(nodes)
    await store.upsert_edges(edges)
    upsert_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    neighbors = await store.neighbors("0", direction="out")
    neighbor_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    persons = await store.query(node_type="N", limit=10)
    query_elapsed = time.perf_counter() - start

    assert len(neighbors) == 101  # 1 NEXT (0->1) + 100 HUB edges
    assert len(persons) == 10
    assert upsert_elapsed < 2.0
    assert neighbor_elapsed < 0.5
    print(
        f"[benchmark] in-memory graph N={n} upsert={upsert_elapsed * 1e3:.2f}ms "
        f"neighbors={neighbor_elapsed * 1e3:.3f}ms query={query_elapsed * 1e3:.3f}ms"
    )
