"""Shared ``GraphStore`` conformance suite reused by every graph store.

``GraphStoreConformance`` is a mixin of async test methods exercising the whole
:class:`GraphStore` contract — ``upsert_nodes`` / ``upsert_edges`` / ``get_node``
/ ``get_edge`` / ``neighbors`` / ``query`` / ``delete_nodes`` / ``delete_edges``
— against whatever store ``make_store`` returns. The in-memory reference and the
Neo4j / Kuzu adapters (behind an in-memory fake backend client) all subclass it,
so one suite guarantees behavioural parity across backends.

``FakeGraphBackendClient`` is a faithful in-memory implementation of the neutral
graph backend-client surface, letting the external adapters run the whole suite
with no driver installed (isolating adapter wiring from vendor query translation,
which is covered separately behind ``needs_*``).

The classes are intentionally NOT named ``Test*`` so pytest does not collect the
abstract base directly; concrete ``Test*`` subclasses inherit its cases.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.graph_stores.graph_backend_client import GraphBackendClient
from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.graph_stores.graph_store import GraphStore


class FakeGraphBackendClient(GraphBackendClient):
    """In-memory neutral graph backend client: adjacency + neutral mappings.

    Faithful enough to run the whole conformance suite against the Neo4j and
    Kuzu adapters with no backend installed.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: dict[str, dict[str, Any]] = {}
        self.closed = False

    async def upsert_nodes(self, nodes: Sequence[Mapping[str, Any]]) -> None:
        for node in nodes:
            self._nodes[node["id"]] = {
                "id": node["id"],
                "type": node["type"],
                "properties": dict(node.get("properties", {})),
            }

    async def upsert_edges(self, edges: Sequence[Mapping[str, Any]]) -> None:
        for edge in edges:
            self._edges[edge["id"]] = {
                "id": edge["id"],
                "source_id": edge["source_id"],
                "target_id": edge["target_id"],
                "type": edge["type"],
                "properties": dict(edge.get("properties", {})),
            }

    async def get_node(self, node_id: str) -> Mapping[str, Any] | None:
        node = self._nodes.get(node_id)
        return dict(node) if node is not None else None

    async def get_edge(self, edge_id: str) -> Mapping[str, Any] | None:
        edge = self._edges.get(edge_id)
        return dict(edge) if edge is not None else None

    async def neighbors(
        self,
        node_id: str,
        *,
        direction: str,
        edge_types: Sequence[str] | None,
        limit: int | None,
    ) -> list[Mapping[str, Any]]:
        allowed = set(edge_types) if edge_types is not None else None
        out: list[Mapping[str, Any]] = []
        for edge in self._edges.values():
            outgoing = edge["source_id"] == node_id
            incoming = edge["target_id"] == node_id
            if direction == "out" and not outgoing:
                continue
            if direction == "in" and not incoming:
                continue
            if direction == "both" and not (outgoing or incoming):
                continue
            if allowed is not None and edge["type"] not in allowed:
                continue
            other_id = edge["target_id"] if outgoing else edge["source_id"]
            other = self._nodes.get(other_id)
            if other is None:
                continue
            out.append({"edge": dict(edge), "node": dict(other)})
            if limit is not None and len(out) >= limit:
                break
        return out

    async def query_nodes(
        self,
        *,
        node_type: str | None,
        properties: Mapping[str, Any] | None,
        limit: int | None,
    ) -> list[Mapping[str, Any]]:
        out: list[Mapping[str, Any]] = []
        for node in self._nodes.values():
            if node_type is not None and node["type"] != node_type:
                continue
            if properties is not None and not all(
                node["properties"].get(key) == value for key, value in properties.items()
            ):
                continue
            out.append(dict(node))
            if limit is not None and len(out) >= limit:
                break
        return out

    async def delete_nodes(self, ids: Sequence[str]) -> None:
        for node_id in ids:
            self._nodes.pop(node_id, None)
            for edge_id in [
                eid
                for eid, edge in self._edges.items()
                if edge["source_id"] == node_id or edge["target_id"] == node_id
            ]:
                self._edges.pop(edge_id, None)

    async def delete_edges(self, ids: Sequence[str]) -> None:
        for edge_id in ids:
            self._edges.pop(edge_id, None)

    async def close(self) -> None:
        self.closed = True


class GraphStoreConformance:
    """Reusable async conformance cases for any :class:`GraphStore`."""

    async def make_store(self) -> GraphStore:
        """Return a fresh, empty store."""
        raise NotImplementedError

    @staticmethod
    def _nodes() -> list[GraphNode]:
        """Return the shared 3-node fixture used by every case."""
        return [
            GraphNode.create(id="a", type="Person", properties={"name": "Ada", "city": "London"}),
            GraphNode.create(id="b", type="Company", properties={"name": "Acme"}),
            GraphNode.create(id="c", type="Person", properties={"name": "Cid", "city": "London"}),
        ]

    @staticmethod
    def _edges() -> list[GraphEdge]:
        """Return the shared edge fixture (a->b works_at, c->a knows)."""
        return [
            GraphEdge.create(
                source_id="a", target_id="b", type="WORKS_AT", properties={"since": 2020}
            ),
            GraphEdge.create(source_id="c", target_id="a", type="KNOWS"),
        ]

    async def _seeded(self) -> GraphStore:
        store = await self.make_store()
        await store.upsert_nodes(self._nodes())
        await store.upsert_edges(self._edges())
        return store

    async def test_upsert_and_get_node_roundtrip(self) -> None:
        store = await self._seeded()
        node = await store.get_node("a")
        assert node is not None
        assert node.id == "a"
        assert node.type == "Person"
        assert node.properties["name"] == "Ada"

    async def test_get_missing_node_returns_none(self) -> None:
        store = await self._seeded()
        assert await store.get_node("nope") is None

    async def test_upsert_and_get_edge_roundtrip(self) -> None:
        store = await self._seeded()
        edge = await store.get_edge("a|WORKS_AT|b")
        assert edge is not None
        assert edge.source_id == "a"
        assert edge.target_id == "b"
        assert edge.type == "WORKS_AT"
        assert edge.properties["since"] == 2020

    async def test_get_missing_edge_returns_none(self) -> None:
        store = await self._seeded()
        assert await store.get_edge("nope") is None

    async def test_neighbors_out(self) -> None:
        store = await self._seeded()
        neighbors = await store.neighbors("a", direction="out")
        assert [n.node.id for n in neighbors] == ["b"]
        assert neighbors[0].edge.type == "WORKS_AT"

    async def test_neighbors_in(self) -> None:
        store = await self._seeded()
        neighbors = await store.neighbors("a", direction="in")
        assert [n.node.id for n in neighbors] == ["c"]
        assert neighbors[0].edge.type == "KNOWS"

    async def test_neighbors_both(self) -> None:
        store = await self._seeded()
        neighbors = await store.neighbors("a", direction="both")
        assert {n.node.id for n in neighbors} == {"b", "c"}

    async def test_neighbors_edge_type_filter(self) -> None:
        store = await self._seeded()
        neighbors = await store.neighbors("a", direction="both", edge_types=["KNOWS"])
        assert [n.node.id for n in neighbors] == ["c"]

    async def test_neighbors_limit(self) -> None:
        store = await self._seeded()
        neighbors = await store.neighbors("a", direction="both", limit=1)
        assert len(neighbors) == 1

    async def test_query_by_type(self) -> None:
        store = await self._seeded()
        nodes = await store.query(node_type="Person")
        assert {n.id for n in nodes} == {"a", "c"}

    async def test_query_by_properties(self) -> None:
        store = await self._seeded()
        nodes = await store.query(node_type="Person", properties={"city": "London"})
        assert {n.id for n in nodes} == {"a", "c"}

    async def test_query_limit(self) -> None:
        store = await self._seeded()
        nodes = await store.query(node_type="Person", limit=1)
        assert len(nodes) == 1

    async def test_upsert_overwrites_node(self) -> None:
        store = await self._seeded()
        await store.upsert_nodes(
            [GraphNode.create(id="a", type="Person", properties={"name": "Ada2"})]
        )
        node = await store.get_node("a")
        assert node is not None
        assert node.properties["name"] == "Ada2"

    async def test_delete_edges(self) -> None:
        store = await self._seeded()
        await store.delete_edges(["a|WORKS_AT|b"])
        assert await store.get_edge("a|WORKS_AT|b") is None
        assert await store.neighbors("a", direction="out") == []

    async def test_delete_nodes_removes_incident_edges(self) -> None:
        store = await self._seeded()
        await store.delete_nodes(["a"])
        assert await store.get_node("a") is None
        # c->a KNOWS and a->b WORKS_AT are both incident to a and must be gone.
        assert await store.get_edge("a|WORKS_AT|b") is None
        assert await store.neighbors("c", direction="out") == []
