"""Contract tests for the :class:`NodeEmbeddingIndex` base class (WS1·S3).

Locks in the house interface style: a ``NotImplementedError`` base class that is
opaque (:class:`PirnOpaqueValue`), with the concrete `GraphEmbeddingIndex`
subclassing it explicitly rather than matching it structurally.
"""

from __future__ import annotations

import unittest

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.graph_rag.graph_embedding_index import GraphEmbeddingIndex
from pirn_agents.graph_rag.node_embedding_index import NodeEmbeddingIndex


class TestNodeEmbeddingIndexContract(unittest.IsolatedAsyncioTestCase):
    def test_base_is_opaque_value(self) -> None:
        # Arrange / Act / Assert: stateful backend bases inherit the opaque contract.
        self.assertTrue(issubclass(NodeEmbeddingIndex, PirnOpaqueValue))

    def test_concrete_index_subclasses_base(self) -> None:
        # Arrange / Act / Assert: the concrete index declares the base nominally.
        self.assertTrue(issubclass(GraphEmbeddingIndex, NodeEmbeddingIndex))

    async def test_base_method_raises_not_implemented(self) -> None:
        # Arrange: a bare base instance (interface style — instantiable, no abc).
        index = NodeEmbeddingIndex()

        # Act / Assert: the abstract method reports the owning class.
        with self.assertRaisesRegex(NotImplementedError, "NodeEmbeddingIndex"):
            await index.ranked_node_ids("q", top_k=3)


if __name__ == "__main__":
    unittest.main()
