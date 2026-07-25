"""``InMemoryGraphStore`` — the zero-dependency adjacency-list reference store.

The default :class:`GraphStore` for tests and examples: it needs no external
service and no backend, keeping nodes and edges in plain dicts with forward /
reverse adjacency indices for O(degree) neighborhood expansion. A real GraphRAG
pipeline runs against this store with no external service; the Neo4j and Kuzu
adapters are validated against the *same* conformance suite so behaviour is
identical.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_neighbor import GraphNeighbor
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.graph_stores.graph_store import GraphStore


class InMemoryGraphStore(GraphStore):
    """An adjacency-list, in-process reference :class:`GraphStore`."""

    def __init__(self) -> None:
        """Initialise an empty in-memory graph."""
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._out: dict[str, list[str]] = {}
        self._in: dict[str, list[str]] = {}

    async def upsert_nodes(self, nodes: Sequence[GraphNode]) -> None:
        """Insert or overwrite each node by id."""
        for node in nodes:
            if not isinstance(node, GraphNode):
                raise TypeError(
                    f"InMemoryGraphStore: nodes must be GraphNode, got {type(node).__name__}"
                )
            self._nodes[node.id] = node

    async def upsert_edges(self, edges: Sequence[GraphEdge]) -> None:
        """Insert or overwrite each edge by id, maintaining adjacency indices."""
        for edge in edges:
            if not isinstance(edge, GraphEdge):
                raise TypeError(
                    f"InMemoryGraphStore: edges must be GraphEdge, got {type(edge).__name__}"
                )
            if edge.id in self._edges:
                self._detach(self._edges[edge.id])
            self._edges[edge.id] = edge
            self._out.setdefault(edge.source_id, []).append(edge.id)
            self._in.setdefault(edge.target_id, []).append(edge.id)

    async def get_node(self, node_id: str) -> GraphNode | None:
        """Return the node stored under ``node_id``, or ``None``."""
        return self._nodes.get(node_id)

    async def get_edge(self, edge_id: str) -> GraphEdge | None:
        """Return the edge stored under ``edge_id``, or ``None``."""
        return self._edges.get(edge_id)

    async def neighbors(
        self,
        node_id: str,
        *,
        direction: str = "out",
        edge_types: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[GraphNeighbor]:
        """Return the one-hop neighbors of ``node_id`` (see :class:`GraphStore`)."""
        if direction not in ("out", "in", "both"):
            raise ValueError(
                f"InMemoryGraphStore: direction must be 'out'|'in'|'both', got {direction!r}"
            )
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ValueError(f"InMemoryGraphStore: limit must be a positive int, got {limit!r}")
        allowed = set(edge_types) if edge_types is not None else None
        out: list[GraphNeighbor] = []
        for edge_id in self._incident_edge_ids(node_id, direction):
            edge = self._edges[edge_id]
            if allowed is not None and edge.type not in allowed:
                continue
            other_id = edge.target_id if edge.source_id == node_id else edge.source_id
            other = self._nodes.get(other_id)
            if other is None:
                continue
            out.append(GraphNeighbor(edge=edge, node=other))
            if limit is not None and len(out) >= limit:
                break
        return out

    async def query(
        self,
        *,
        node_type: str | None = None,
        properties: Mapping[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[GraphNode]:
        """Return nodes matching ``node_type`` and every ``properties`` entry."""
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ValueError(f"InMemoryGraphStore: limit must be a positive int, got {limit!r}")
        out: list[GraphNode] = []
        for node in self._nodes.values():
            if node_type is not None and node.type != node_type:
                continue
            if properties is not None and not self._matches(node.properties, properties):
                continue
            out.append(node)
            if limit is not None and len(out) >= limit:
                break
        return out

    async def delete_nodes(self, ids: Sequence[str]) -> None:
        """Remove each node in ``ids`` along with its incident edges."""
        for node_id in ids:
            incident = set(self._out.get(node_id, [])) | set(self._in.get(node_id, []))
            for edge_id in incident:
                edge = self._edges.pop(edge_id, None)
                if edge is not None:
                    self._detach(edge)
            self._nodes.pop(node_id, None)
            self._out.pop(node_id, None)
            self._in.pop(node_id, None)

    async def delete_edges(self, ids: Sequence[str]) -> None:
        """Remove each edge in ``ids`` and drop it from the adjacency indices."""
        for edge_id in ids:
            edge = self._edges.pop(edge_id, None)
            if edge is not None:
                self._detach(edge)

    async def close(self) -> None:
        """Drop all nodes, edges, and adjacency indices."""
        self._nodes.clear()
        self._edges.clear()
        self._out.clear()
        self._in.clear()

    def _incident_edge_ids(self, node_id: str, direction: str) -> list[str]:
        """Return the incident edge ids for ``node_id`` in ``direction``."""
        if direction == "out":
            return list(self._out.get(node_id, []))
        if direction == "in":
            return list(self._in.get(node_id, []))
        return list(self._out.get(node_id, [])) + list(self._in.get(node_id, []))

    def _detach(self, edge: GraphEdge) -> None:
        """Remove ``edge`` from the forward / reverse adjacency indices."""
        outgoing = self._out.get(edge.source_id)
        if outgoing is not None and edge.id in outgoing:
            outgoing.remove(edge.id)
        incoming = self._in.get(edge.target_id)
        if incoming is not None and edge.id in incoming:
            incoming.remove(edge.id)

    @staticmethod
    def _matches(properties: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
        """Return whether ``properties`` contains every ``expected`` key/value."""
        return all(properties.get(key) == value for key, value in expected.items())
