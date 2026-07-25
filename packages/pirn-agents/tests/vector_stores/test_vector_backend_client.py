"""Contract tests for the :class:`VectorBackendClient` base class (WS1·S1).

Locks in the house interface style: a ``NotImplementedError`` base class that is
opaque (:class:`PirnOpaqueValue`), with concrete vendor wrappers subclassing it
explicitly rather than matching it structurally.
"""

from __future__ import annotations

import unittest

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.vector_stores.chroma_backend_client import ChromaBackendClient
from pirn_agents.vector_stores.qdrant_backend_client import QdrantBackendClient
from pirn_agents.vector_stores.vector_backend_client import VectorBackendClient


class TestVectorBackendClientContract(unittest.IsolatedAsyncioTestCase):
    def test_base_is_opaque_value(self) -> None:
        # Arrange / Act / Assert: stateful backend bases inherit the opaque contract.
        self.assertTrue(issubclass(VectorBackendClient, PirnOpaqueValue))

    def test_vendor_wrappers_subclass_base(self) -> None:
        # Arrange / Act / Assert: concrete wrappers declare the base nominally.
        self.assertTrue(issubclass(ChromaBackendClient, VectorBackendClient))
        self.assertTrue(issubclass(QdrantBackendClient, VectorBackendClient))

    async def test_base_methods_raise_not_implemented(self) -> None:
        # Arrange: a bare base instance (interface style — instantiable, no abc).
        client = VectorBackendClient()

        # Act / Assert: every method reports the owning class in its message.
        with self.assertRaisesRegex(NotImplementedError, "VectorBackendClient"):
            await client.upsert_points([])
        with self.assertRaisesRegex(NotImplementedError, "VectorBackendClient"):
            await client.search_points([1.0], top_k=1, metadata_filter=None)
        with self.assertRaisesRegex(NotImplementedError, "VectorBackendClient"):
            await client.get_point("x")
        with self.assertRaisesRegex(NotImplementedError, "VectorBackendClient"):
            await client.delete_points(["x"])
        with self.assertRaisesRegex(NotImplementedError, "VectorBackendClient"):
            await client.close()
