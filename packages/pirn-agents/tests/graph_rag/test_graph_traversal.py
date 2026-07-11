"""Tests for the :class:`GraphTraversal` knot (S4 k-hop + path queries)."""

from __future__ import annotations

import unittest

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
        object.__setattr__(knot, "_config", KnotConfig(id="traverse"))
    return knot


async def _chain_store() -> InMemoryGraphStore:
    """a->b->c->d (NEXT) plus a->e (SIDE)."""
    store = InMemoryGraphStore()
    await store.upsert_nodes(
        [
            GraphNode.create(id=n, type="N", properties={"name": n})
            for n in ("a", "b", "c", "d", "e")
        ]
    )
    await store.upsert_edges(
        [
            GraphEdge.create(source_id="a", target_id="b", type="NEXT"),
            GraphEdge.create(source_id="b", target_id="c", type="NEXT"),
            GraphEdge.create(source_id="c", target_id="d", type="NEXT"),
            GraphEdge.create(source_id="a", target_id="e", type="SIDE"),
        ]
    )
    return store


class TestGraphTraversalNeighborhood(unittest.IsolatedAsyncioTestCase):
    async def test_one_hop_out(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        budget = TraversalBudget.create(max_depth=1, max_fanout=10, max_nodes=100)
        subgraph = await traversal.process(
            start_ids=["a"], store=store, budget=budget, direction="out"
        )
        assert set(subgraph.node_ids()) == {"a", "b", "e"}
        assert {e.id for e in subgraph.edges} == {"a|NEXT|b", "a|SIDE|e"}

    async def test_two_hop_out_grows_frontier(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        budget = TraversalBudget.create(max_depth=2, max_fanout=10, max_nodes=100)
        subgraph = await traversal.process(
            start_ids=["a"], store=store, budget=budget, direction="out"
        )
        assert set(subgraph.node_ids()) == {"a", "b", "e", "c"}

    async def test_fanout_bounds_neighbors_per_node(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        budget = TraversalBudget.create(max_depth=1, max_fanout=1, max_nodes=100)
        subgraph = await traversal.process(
            start_ids=["a"], store=store, budget=budget, direction="out"
        )
        # a has two out-edges but fanout caps expansion to one neighbor.
        assert len(subgraph.node_ids()) == 2

    async def test_max_nodes_caps_total(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        budget = TraversalBudget.create(max_depth=5, max_fanout=10, max_nodes=2)
        subgraph = await traversal.process(
            start_ids=["a"], store=store, budget=budget, direction="out"
        )
        assert len(subgraph.node_ids()) == 2

    async def test_edge_type_filter(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        budget = TraversalBudget.create(max_depth=1, max_fanout=10, max_nodes=100)
        subgraph = await traversal.process(
            start_ids=["a"], store=store, budget=budget, direction="out", edge_types=["SIDE"]
        )
        assert set(subgraph.node_ids()) == {"a", "e"}

    async def test_no_dangling_edges_under_node_cap(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        budget = TraversalBudget.create(max_depth=5, max_fanout=10, max_nodes=2)
        subgraph = await traversal.process(
            start_ids=["a"], store=store, budget=budget, direction="out"
        )
        node_ids = set(subgraph.node_ids())
        for edge in subgraph.edges:
            assert edge.source_id in node_ids
            assert edge.target_id in node_ids

    async def test_rejects_empty_start_ids(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        with self.assertRaisesRegex(ValueError, "start_ids must be non-empty"):
            await traversal.process(start_ids=[], store=store, budget=TraversalBudget.create())

    async def test_rejects_bad_store(self) -> None:
        traversal = _make_traversal()
        with self.assertRaisesRegex(TypeError, "store must be a GraphStore"):
            await traversal.process(
                start_ids=["a"],
                store="nope",  # type: ignore[arg-type]
                budget=TraversalBudget.create(),
            )

    async def test_rejects_bad_budget(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        with self.assertRaisesRegex(TypeError, "budget must be a TraversalBudget"):
            await traversal.process(
                start_ids=["a"],
                store=store,
                budget="nope",  # type: ignore[arg-type]
            )


class TestGraphTraversalPathQuery(unittest.IsolatedAsyncioTestCase):
    async def test_finds_shortest_path(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        budget = TraversalBudget.create(max_depth=5, max_fanout=10, max_nodes=100)
        path = await traversal.shortest_path("a", "d", store=store, budget=budget, direction="out")
        assert path == ["a", "b", "c", "d"]

    async def test_path_bounded_by_depth(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        budget = TraversalBudget.create(max_depth=2, max_fanout=10, max_nodes=100)
        path = await traversal.shortest_path("a", "d", store=store, budget=budget, direction="out")
        assert path is None

    async def test_source_equals_target(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        path = await traversal.shortest_path("a", "a", store=store, budget=TraversalBudget.create())
        assert path == ["a"]

    def test_budget_rejects_non_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_depth must be a positive int"):
            TraversalBudget.create(max_depth=0)


if __name__ == "__main__":
    unittest.main()
