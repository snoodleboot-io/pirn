"""Tests for :class:`InMemoryGraphStore` (S1 reference impl + conformance)."""

from __future__ import annotations

import unittest

from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.graph_stores.graph_store import GraphStore
from pirn_agents.graph_stores.in_memory_graph_store import InMemoryGraphStore
from tests.graph_stores.conformance import GraphStoreConformance


class TestInMemoryGraphStoreConformance(GraphStoreConformance):
    async def make_store(self) -> GraphStore:
        return InMemoryGraphStore()


class TestInMemoryGraphStoreSpecifics(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_bad_direction(self) -> None:
        store = InMemoryGraphStore()
        await store.upsert_nodes([GraphNode.create(id="a", type="T")])
        with self.assertRaisesRegex(ValueError, "direction must be"):
            await store.neighbors("a", direction="sideways")

    async def test_rejects_non_positive_limit(self) -> None:
        store = InMemoryGraphStore()
        with self.assertRaisesRegex(ValueError, "limit must be a positive int"):
            await store.query(limit=0)

    async def test_rejects_non_graph_node(self) -> None:
        store = InMemoryGraphStore()
        with self.assertRaisesRegex(TypeError, "nodes must be GraphNode"):
            await store.upsert_nodes(["nope"])  # type: ignore[list-item]

    async def test_rejects_non_graph_edge(self) -> None:
        store = InMemoryGraphStore()
        with self.assertRaisesRegex(TypeError, "edges must be GraphEdge"):
            await store.upsert_edges(["nope"])  # type: ignore[list-item]

    async def test_upsert_edge_overwrite_keeps_single_adjacency(self) -> None:
        store = InMemoryGraphStore()
        await store.upsert_nodes(
            [GraphNode.create(id="a", type="T"), GraphNode.create(id="b", type="T")]
        )
        edge = GraphEdge.create(source_id="a", target_id="b", type="R")
        await store.upsert_edges([edge, edge])
        neighbors = await store.neighbors("a", direction="out")
        # Re-upserting the same edge id must not duplicate the adjacency entry.
        assert len(neighbors) == 1

    async def test_neighbor_missing_target_is_skipped(self) -> None:
        store = InMemoryGraphStore()
        await store.upsert_nodes([GraphNode.create(id="a", type="T")])
        await store.upsert_edges([GraphEdge.create(source_id="a", target_id="ghost", type="R")])
        # Target node was never upserted, so the dangling edge yields no neighbor.
        assert await store.neighbors("a", direction="out") == []

    async def test_close_clears_graph(self) -> None:
        store = InMemoryGraphStore()
        await store.upsert_nodes([GraphNode.create(id="a", type="T")])
        await store.close()
        assert await store.get_node("a") is None

    def test_graph_node_create_rejects_empty_id(self) -> None:
        with self.assertRaisesRegex(TypeError, "id must be a non-empty str"):
            GraphNode.create(id="", type="T")

    def test_graph_edge_create_derives_deterministic_id(self) -> None:
        edge = GraphEdge.create(source_id="a", target_id="b", type="R")
        assert edge.id == "a|R|b"

    def test_graph_edge_create_rejects_empty_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "type must be a non-empty str"):
            GraphEdge.create(source_id="a", target_id="b", type="")


if __name__ == "__main__":
    unittest.main()
