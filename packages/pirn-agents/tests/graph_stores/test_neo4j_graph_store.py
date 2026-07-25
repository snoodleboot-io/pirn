"""Tests for :class:`Neo4jGraphStore` (S2 adapter behind the ``[neo4j]`` extra).

The full shared conformance suite runs against the adapter wired to an in-memory
neutral fake backend (no ``neo4j`` imported). A ``needs_neo4j`` case runs the same
intent against a real Neo4j when configured, a guard proves importing the store
leaves the backend unimported, and a simulated-absence case proves the friendly
install error is raised.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

import pytest

from pirn_agents.graph_stores.graph_store import GraphStore
from pirn_agents.graph_stores.neo4j_graph_store import Neo4jGraphStore
from tests.graph_stores.conformance import FakeGraphBackendClient, GraphStoreConformance


class TestNeo4jConformance(GraphStoreConformance):
    async def make_store(self) -> GraphStore:
        return Neo4jGraphStore(client=FakeGraphBackendClient())


class TestNeo4jStoreSpecifics(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_backend_client(self) -> None:
        client = FakeGraphBackendClient()
        store = Neo4jGraphStore(client=client)
        await store.close()
        assert client.closed is True

    def test_import_does_not_pull_backend(self) -> None:
        assert "neo4j" not in sys.modules

    async def test_missing_backend_raises_friendly_error(self) -> None:
        # CI installs the [neo4j] extra, so simulate absence by masking the
        # module, then force the real client-build path (no injected client).
        store = Neo4jGraphStore(uri="bolt://localhost:7687")
        with patch.dict(sys.modules, {"neo4j": None}):
            with self.assertRaisesRegex(ImportError, r'pip install "pirn-agents\[neo4j\]"'):
                await store.get_node("a")

    async def test_rejects_bad_direction(self) -> None:
        store = Neo4jGraphStore(client=FakeGraphBackendClient())
        with self.assertRaisesRegex(ValueError, "direction must be"):
            await store.neighbors("a", direction="sideways")


@pytest.mark.needs_neo4j
class TestNeo4jRealBackend(unittest.IsolatedAsyncioTestCase):
    async def test_conformance_against_real_neo4j(self) -> None:
        uri = os.environ.get("PIRN_TEST_NEO4J_URL")
        if not uri:
            self.skipTest("PIRN_TEST_NEO4J_URL not set")
        from pirn_agents.graph_stores.graph_node import GraphNode

        store = Neo4jGraphStore(uri=uri)
        await store.upsert_nodes([GraphNode.create(id="a", type="Person")])
        node = await store.get_node("a")
        assert node is not None and node.id == "a"
        await store.close()


if __name__ == "__main__":
    unittest.main()
