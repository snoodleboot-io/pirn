"""Tests for the :class:`GraphTraversal` and :class:`GraphShortestPath` knots.

Both are ``SubTapestry`` knots since PIR-874: each store query is a knot of its
own and each hop is a ``LoopSubTapestry`` iteration, so ``process()`` returns a
sink rather than a finished answer. These tests therefore run a real graph —
which is also what pins that the hop fan-out reproduces the sequential
traversal's results exactly (the running ``max_nodes`` cap and "first path to
the target" both depend on order).
"""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.retrieval.graph_rag.graph_shortest_path import GraphShortestPath
from pirn_agents.retrieval.graph_rag.graph_traversal import GraphTraversal
from pirn_agents.retrieval.graph_rag.subgraph import Subgraph
from pirn_agents.retrieval.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.retrieval.graph_stores.graph_edge import GraphEdge
from pirn_agents.retrieval.graph_stores.graph_node import GraphNode
from pirn_agents.retrieval.graph_stores.in_memory_graph_store import InMemoryGraphStore


def _make_traversal() -> GraphTraversal:
    with Tapestry():
        knot = GraphTraversal(
            start_ids=["a"],
            store=InMemoryGraphStore(),
            budget=TraversalBudget.create(),
            direction="both",
            edge_types=None,
            _config=KnotConfig(id="traverse"),
        )
    return knot


async def _traverse(
    store: InMemoryGraphStore,
    budget: TraversalBudget,
    *,
    start_ids: list[str] | None = None,
    direction: str = "out",
    edge_types: list[str] | None = None,
) -> Subgraph:
    """Run a traversal as a real graph and return the subgraph it collected."""
    with Tapestry() as tapestry:
        GraphTraversal(
            start_ids=start_ids if start_ids is not None else ["a"],
            store=store,
            budget=budget,
            direction=direction,
            edge_types=edge_types,
            _config=KnotConfig(id="traverse"),
        )
        result = await tapestry.run(RunRequest())
    assert result.succeeded, result.exceptions
    return result.outputs["traverse"]


async def _shortest_path(
    store: InMemoryGraphStore,
    source_id: str,
    target_id: str,
    budget: TraversalBudget,
    *,
    direction: str = "both",
) -> list[str] | None:
    """Run a path query as a real graph and return the path it found."""
    with Tapestry() as tapestry:
        GraphShortestPath(
            source_id=source_id,
            target_id=target_id,
            store=store,
            budget=budget,
            direction=direction,
            _config=KnotConfig(id="path"),
        )
        result = await tapestry.run(RunRequest())
    assert result.succeeded, result.exceptions
    return result.outputs["path"]


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
        budget = TraversalBudget.create(max_depth=1, max_fanout=10, max_nodes=100)
        subgraph = await _traverse(store, budget)
        assert set(subgraph.node_ids()) == {"a", "b", "e"}
        assert {e.id for e in subgraph.edges} == {"a|NEXT|b", "a|SIDE|e"}

    async def test_two_hop_out_grows_frontier(self) -> None:
        store = await _chain_store()
        budget = TraversalBudget.create(max_depth=2, max_fanout=10, max_nodes=100)
        subgraph = await _traverse(store, budget)
        assert set(subgraph.node_ids()) == {"a", "b", "e", "c"}

    async def test_fanout_bounds_neighbors_per_node(self) -> None:
        store = await _chain_store()
        budget = TraversalBudget.create(max_depth=1, max_fanout=1, max_nodes=100)
        subgraph = await _traverse(store, budget)
        # a has two out-edges but fanout caps expansion to one neighbor.
        assert len(subgraph.node_ids()) == 2

    async def test_max_nodes_caps_total(self) -> None:
        store = await _chain_store()
        budget = TraversalBudget.create(max_depth=5, max_fanout=10, max_nodes=2)
        subgraph = await _traverse(store, budget)
        assert len(subgraph.node_ids()) == 2

    async def test_edge_type_filter(self) -> None:
        store = await _chain_store()
        budget = TraversalBudget.create(max_depth=1, max_fanout=10, max_nodes=100)
        subgraph = await _traverse(store, budget, edge_types=["SIDE"])
        assert set(subgraph.node_ids()) == {"a", "e"}

    async def test_no_dangling_edges_under_node_cap(self) -> None:
        store = await _chain_store()
        budget = TraversalBudget.create(max_depth=5, max_fanout=10, max_nodes=2)
        subgraph = await _traverse(store, budget)
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
        result = await traversal(
            {"start_ids": ["a"], "store": "nope", "budget": TraversalBudget.create()}
        )
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_rejects_bad_budget(self) -> None:
        store = await _chain_store()
        traversal = _make_traversal()
        result = await traversal({"start_ids": ["a"], "store": store, "budget": "nope"})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"


class TestGraphShortestPath(unittest.IsolatedAsyncioTestCase):
    async def test_finds_shortest_path(self) -> None:
        store = await _chain_store()
        budget = TraversalBudget.create(max_depth=5, max_fanout=10, max_nodes=100)
        path = await _shortest_path(store, "a", "d", budget, direction="out")
        assert path == ["a", "b", "c", "d"]

    async def test_path_bounded_by_depth(self) -> None:
        store = await _chain_store()
        budget = TraversalBudget.create(max_depth=2, max_fanout=10, max_nodes=100)
        path = await _shortest_path(store, "a", "d", budget, direction="out")
        assert path is None

    async def test_source_equals_target(self) -> None:
        """No query at all: the seeded state already carries the answer."""
        store = await _chain_store()
        path = await _shortest_path(store, "a", "a", TraversalBudget.create())
        assert path == ["a"]

    async def test_unreachable_target_is_none(self) -> None:
        store = await _chain_store()
        budget = TraversalBudget.create(max_depth=5, max_fanout=10, max_nodes=100)
        path = await _shortest_path(store, "e", "d", budget, direction="out")
        assert path is None

    def test_budget_rejects_non_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_depth must be a positive int"):
            TraversalBudget.create(max_depth=0)


if __name__ == "__main__":
    unittest.main()
