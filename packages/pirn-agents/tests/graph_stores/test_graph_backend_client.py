"""Contract tests for the :class:`GraphBackendClient` base class (WS1·S1).

Locks in the house interface style: a ``NotImplementedError`` base class that is
opaque (:class:`PirnOpaqueValue`), with concrete vendor wrappers subclassing it
explicitly rather than matching it structurally.
"""

from __future__ import annotations

import unittest

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.graph_stores.graph_backend_client import GraphBackendClient
from pirn_agents.graph_stores.kuzu_backend_client import KuzuBackendClient
from pirn_agents.graph_stores.neo4j_backend_client import Neo4jBackendClient


class TestGraphBackendClientContract(unittest.IsolatedAsyncioTestCase):
    def test_base_is_opaque_value(self) -> None:
        # Arrange / Act / Assert: stateful backend bases inherit the opaque contract.
        self.assertTrue(issubclass(GraphBackendClient, PirnOpaqueValue))

    def test_vendor_wrappers_subclass_base(self) -> None:
        # Arrange / Act / Assert: concrete wrappers declare the base nominally.
        self.assertTrue(issubclass(Neo4jBackendClient, GraphBackendClient))
        self.assertTrue(issubclass(KuzuBackendClient, GraphBackendClient))

    async def test_base_methods_raise_not_implemented(self) -> None:
        # Arrange: a bare base instance (interface style — instantiable, no abc).
        client = GraphBackendClient()

        # Act / Assert: every method reports the owning class in its message.
        with self.assertRaisesRegex(NotImplementedError, "GraphBackendClient"):
            await client.upsert_nodes([])
        with self.assertRaisesRegex(NotImplementedError, "GraphBackendClient"):
            await client.upsert_edges([])
        with self.assertRaisesRegex(NotImplementedError, "GraphBackendClient"):
            await client.get_node("x")
        with self.assertRaisesRegex(NotImplementedError, "GraphBackendClient"):
            await client.get_edge("x")
        with self.assertRaisesRegex(NotImplementedError, "GraphBackendClient"):
            await client.neighbors("x", direction="out", edge_types=None, limit=None)
        with self.assertRaisesRegex(NotImplementedError, "GraphBackendClient"):
            await client.query_nodes(node_type=None, properties=None, limit=None)
        with self.assertRaisesRegex(NotImplementedError, "GraphBackendClient"):
            await client.delete_nodes(["x"])
        with self.assertRaisesRegex(NotImplementedError, "GraphBackendClient"):
            await client.delete_edges(["x"])
        with self.assertRaisesRegex(NotImplementedError, "GraphBackendClient"):
            await client.close()
