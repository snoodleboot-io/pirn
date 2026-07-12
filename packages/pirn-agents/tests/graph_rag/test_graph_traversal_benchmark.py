"""Benchmark: traversal latency vs. graph size / budget (S4-T3).

Builds a star hub with a large fan-out over a big node set and proves the
:class:`TraversalBudget` bounds the work: a depth-1 traversal with a small
``max_fanout`` / ``max_nodes`` visits only budget-many nodes and stays fast
regardless of the total graph size. Measured figures are printed for an
F10-style report.
"""

from __future__ import annotations

import time

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.graph_rag.graph_traversal import GraphTraversal
from pirn_agents.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.graph_stores.in_memory_graph_store import InMemoryGraphStore


def _make_traversal() -> GraphTraversal:
    with Tapestry():
        knot = GraphTraversal.__new__(GraphTraversal)
        object.__setattr__(knot, "_config", KnotConfig(id="traverse-bench"))
    return knot


@pytest.mark.benchmark
async def test_budget_bounds_traversal_work() -> None:
    n = 10_000
    store = InMemoryGraphStore()
    await store.upsert_nodes([GraphNode.create(id=str(i), type="N") for i in range(n)])
    # Hub node "0" is connected to every other node — a huge raw fan-out.
    await store.upsert_edges(
        [GraphEdge.create(source_id="0", target_id=str(i), type="HUB") for i in range(1, n)]
    )
    traversal = _make_traversal()

    budget = TraversalBudget.create(max_depth=1, max_fanout=25, max_nodes=25)
    start = time.perf_counter()
    subgraph = await traversal.process(start_ids=["0"], store=store, budget=budget, direction="out")
    elapsed = time.perf_counter() - start

    # The budget — not the graph size — bounds the result and the latency.
    assert len(subgraph.node_ids()) <= 25
    assert elapsed < 0.5
    print(
        f"[benchmark] traversal N={n} depth=1 fanout=25 nodes={len(subgraph.node_ids())} "
        f"latency={elapsed * 1e3:.3f}ms"
    )
