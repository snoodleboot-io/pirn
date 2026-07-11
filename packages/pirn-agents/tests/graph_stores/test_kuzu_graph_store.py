"""Tests for :class:`KuzuGraphStore` (S2 adapter behind the ``[kuzu]`` extra).

The full shared conformance suite runs against the adapter wired to an in-memory
neutral fake backend (no ``kuzu`` imported). A ``needs_kuzu`` case runs the same
intent against a real embedded Kuzu when installed, a guard proves importing the
store leaves the backend unimported, and a simulated-absence case proves the
friendly install error is raised.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

import pytest

from pirn_agents.graph_stores.graph_store import GraphStore
from pirn_agents.graph_stores.kuzu_graph_store import KuzuGraphStore
from tests.graph_stores.conformance import FakeGraphBackendClient, GraphStoreConformance


class TestKuzuConformance(GraphStoreConformance):
    async def make_store(self) -> GraphStore:
        return KuzuGraphStore(client=FakeGraphBackendClient())


class TestKuzuStoreSpecifics(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_backend_client(self) -> None:
        client = FakeGraphBackendClient()
        store = KuzuGraphStore(client=client)
        await store.close()
        assert client.closed is True

    def test_import_does_not_pull_backend(self) -> None:
        assert "kuzu" not in sys.modules

    async def test_missing_backend_raises_friendly_error(self) -> None:
        # CI installs the [kuzu] extra, so simulate absence by masking the
        # module, then force the real client-build path (no injected client).
        store = KuzuGraphStore()
        with patch.dict(sys.modules, {"kuzu": None}):
            with self.assertRaisesRegex(ImportError, r'pip install "pirn-agents\[kuzu\]"'):
                await store.get_node("a")


@pytest.mark.needs_kuzu
class TestKuzuRealBackend(unittest.IsolatedAsyncioTestCase):
    async def test_conformance_against_real_kuzu(self) -> None:
        from pirn_agents.graph_stores.graph_node import GraphNode

        store = KuzuGraphStore(db_path=":memory:")
        await store.upsert_nodes([GraphNode.create(id="a", type="Person")])
        node = await store.get_node("a")
        assert node is not None and node.id == "a"
        await store.close()


if __name__ == "__main__":
    unittest.main()
