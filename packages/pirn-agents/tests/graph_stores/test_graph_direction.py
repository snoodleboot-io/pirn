"""Characterisation tests for the graph neighbour-direction vocabulary.

Pins the accepted values, the rejection message shape, and the point at which
each layer rejects a bad direction — including the *backend clients*, which
historically raised a bare ``KeyError`` from an inline arrow map rather than the
explicit ``ValueError`` the store layer raises.
"""

from __future__ import annotations

import unittest

from pirn_agents.retrieval.graph_stores.graph_direction import GraphDirection
from pirn_agents.retrieval.graph_stores.graph_edge import GraphEdge
from pirn_agents.retrieval.graph_stores.graph_node import GraphNode
from pirn_agents.retrieval.graph_stores.in_memory_graph_store import InMemoryGraphStore
from pirn_agents.retrieval.graph_stores.kuzu_backend_client import KuzuBackendClient
from pirn_agents.retrieval.graph_stores.neo4j_backend_client import Neo4jBackendClient
from pirn_agents.retrieval.graph_stores.neo4j_graph_store import Neo4jGraphStore
from tests.graph_stores.conformance import FakeGraphBackendClient


async def _seeded() -> InMemoryGraphStore:
    """Return an in-memory store with a->b and c->a edges around node ``a``."""
    store = InMemoryGraphStore()
    await store.upsert_nodes(
        [
            GraphNode.create(id="a", type="Person"),
            GraphNode.create(id="b", type="Company"),
            GraphNode.create(id="c", type="Person"),
        ]
    )
    await store.upsert_edges(
        [
            GraphEdge.create(source_id="a", target_id="b", type="WORKS_AT"),
            GraphEdge.create(source_id="c", target_id="a", type="KNOWS"),
        ]
    )
    return store


class TestAcceptedDirections(unittest.IsolatedAsyncioTestCase):
    async def test_out_follows_only_outgoing_edges(self) -> None:
        # Arrange / Act / Assert
        store = await _seeded()
        assert [n.node.id for n in await store.neighbors("a", direction="out")] == ["b"]

    async def test_in_follows_only_incoming_edges(self) -> None:
        # Arrange / Act / Assert
        store = await _seeded()
        assert [n.node.id for n in await store.neighbors("a", direction="in")] == ["c"]

    async def test_both_follows_outgoing_then_incoming(self) -> None:
        # Arrange / Act / Assert: forward adjacency precedes reverse adjacency.
        store = await _seeded()
        assert [n.node.id for n in await store.neighbors("a", direction="both")] == ["b", "c"]

    async def test_out_is_the_store_default(self) -> None:
        # Arrange / Act / Assert
        store = await _seeded()
        assert [n.node.id for n in await store.neighbors("a")] == ["b"]


class TestRejectedDirections(unittest.IsolatedAsyncioTestCase):
    async def test_in_memory_store_rejects_with_owner_prefixed_value_error(self) -> None:
        # Arrange / Act / Assert
        store = await _seeded()
        with self.assertRaisesRegex(
            ValueError, r"InMemoryGraphStore: direction must be 'out'\|'in'\|'both', got 'sideways'"
        ):
            await store.neighbors("a", direction="sideways")

    async def test_backend_store_rejects_with_owner_prefixed_value_error(self) -> None:
        # Arrange / Act / Assert: the concrete adapter names itself, not the base.
        store = Neo4jGraphStore(client=FakeGraphBackendClient())
        with self.assertRaisesRegex(
            ValueError, r"Neo4jGraphStore: direction must be 'out'\|'in'\|'both', got 'sideways'"
        ):
            await store.neighbors("a", direction="sideways")

    async def test_neo4j_backend_client_rejects_before_touching_the_driver(self) -> None:
        # Arrange: no driver is installed/needed — the direction is validated first.
        client = Neo4jBackendClient(uri="bolt://localhost:7687")

        # Act / Assert
        with self.assertRaisesRegex(
            ValueError,
            r"Neo4jBackendClient: direction must be 'out'\|'in'\|'both', got 'sideways'",
        ):
            await client.neighbors("a", direction="sideways", edge_types=None, limit=None)

    async def test_kuzu_backend_client_rejects_before_touching_the_driver(self) -> None:
        # Arrange
        client = KuzuBackendClient()

        # Act / Assert
        with self.assertRaisesRegex(
            ValueError,
            r"KuzuBackendClient: direction must be 'out'\|'in'\|'both', got 'sideways'",
        ):
            await client.neighbors("a", direction="sideways", edge_types=None, limit=None)


class TestGraphDirectionEnum(unittest.TestCase):
    def test_values_are_plain_strings(self) -> None:
        # Arrange / Act / Assert: the str mixin keeps `==` against raw literals working.
        assert GraphDirection.OUT == "out"
        assert GraphDirection.IN == "in"
        assert GraphDirection.BOTH == "both"

    def test_vocabulary_is_exactly_the_historical_tuple(self) -> None:
        # Arrange / Act / Assert: byte-identical to the replaced ("out", "in", "both").
        assert [member.value for member in GraphDirection] == ["out", "in", "both"]

    def test_parse_returns_the_matching_member(self) -> None:
        # Arrange / Act / Assert
        assert GraphDirection.parse("out", owner="X") is GraphDirection.OUT
        assert GraphDirection.parse("in", owner="X") is GraphDirection.IN
        assert GraphDirection.parse("both", owner="X") is GraphDirection.BOTH

    def test_parse_reports_the_owner_in_the_error(self) -> None:
        # Arrange / Act / Assert: the message names the layer the caller invoked.
        with self.assertRaisesRegex(
            ValueError, r"SomeStore: direction must be 'out'\|'in'\|'both', got 'up'"
        ):
            GraphDirection.parse("up", owner="SomeStore")

    def test_parse_rejects_case_variants_and_members_of_other_types(self) -> None:
        # Arrange / Act / Assert: the vocabulary is exact, not lenient.
        with self.assertRaises(ValueError):
            GraphDirection.parse("OUT", owner="SomeStore")
        with self.assertRaises(ValueError):
            GraphDirection.parse("", owner="SomeStore")


if __name__ == "__main__":
    unittest.main()
