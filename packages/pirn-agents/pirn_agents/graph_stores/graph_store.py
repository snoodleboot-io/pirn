"""``GraphStore`` — the provider-neutral knowledge-graph store interface.

Every concrete graph store (in-memory reference, Neo4j, Kuzu) shares one
graph-native contract expressed as async coroutines:

* :meth:`upsert_nodes` / :meth:`upsert_edges` — write :class:`GraphNode` /
  :class:`GraphEdge` batches idempotently by id;
* :meth:`get_node` / :meth:`get_edge` — fetch a single element by id;
* :meth:`neighbors` — the one-hop traversal primitive: the adjacent
  :class:`GraphNeighbor` set of a node, bounded by direction / edge-type / count;
* :meth:`query` — a neutral node match by type and property equality;
* :meth:`delete_nodes` / :meth:`delete_edges` — remove elements by id.

The interface is opaque (:class:`PirnOpaqueValue`) so a store drops into the
pirn graph as a config value without entering the content-addressed hash. A
single shared conformance suite exercises exactly these methods, which is why
the in-memory reference and the external adapters are validated identically.
The higher-level traversal, extraction, and hybrid-retrieval knots depend only
on this interface, never on a concrete backend.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_neighbor import GraphNeighbor
from pirn_agents.graph_stores.graph_node import GraphNode


class GraphStore(PirnOpaqueValue):
    """Abstract knowledge-graph store exposing the neutral graph contract."""

    async def upsert_nodes(self, nodes: Sequence[GraphNode]) -> None:
        """Insert or overwrite each node by id."""
        raise NotImplementedError(f"{type(self).__name__} must implement upsert_nodes()")

    async def upsert_edges(self, edges: Sequence[GraphEdge]) -> None:
        """Insert or overwrite each edge by id."""
        raise NotImplementedError(f"{type(self).__name__} must implement upsert_edges()")

    async def get_node(self, node_id: str) -> GraphNode | None:
        """Return the node stored under ``node_id``, or ``None``."""
        raise NotImplementedError(f"{type(self).__name__} must implement get_node()")

    async def get_edge(self, edge_id: str) -> GraphEdge | None:
        """Return the edge stored under ``edge_id``, or ``None``."""
        raise NotImplementedError(f"{type(self).__name__} must implement get_edge()")

    async def neighbors(
        self,
        node_id: str,
        *,
        direction: str = "out",
        edge_types: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[GraphNeighbor]:
        """Return the one-hop neighbors of ``node_id``.

        Args:
            node_id: The node whose neighborhood is expanded.
            direction: ``"out"`` (edges leaving ``node_id``), ``"in"`` (edges
                arriving at ``node_id``), or ``"both"``.
            edge_types: Optional whitelist of edge types to traverse; ``None``
                traverses every type.
            limit: Optional cap on the number of neighbors returned.

        Returns:
            The adjacent :class:`GraphNeighbor` set (edge + reached node).
        """
        raise NotImplementedError(f"{type(self).__name__} must implement neighbors()")

    async def query(
        self,
        *,
        node_type: str | None = None,
        properties: Mapping[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[GraphNode]:
        """Return nodes matching ``node_type`` and every ``properties`` entry.

        Args:
            node_type: Optional exact node-type match; ``None`` matches any type.
            properties: Optional property-equality filter; every key must be
                present and equal on a matching node.
            limit: Optional cap on the number of nodes returned.

        Returns:
            The matching nodes (order is implementation-defined but stable).
        """
        raise NotImplementedError(f"{type(self).__name__} must implement query()")

    async def delete_nodes(self, ids: Sequence[str]) -> None:
        """Remove every node whose id is in ``ids`` and its incident edges."""
        raise NotImplementedError(f"{type(self).__name__} must implement delete_nodes()")

    async def delete_edges(self, ids: Sequence[str]) -> None:
        """Remove every edge whose id is in ``ids`` (missing ids are ignored)."""
        raise NotImplementedError(f"{type(self).__name__} must implement delete_edges()")

    async def close(self) -> None:
        """Release any underlying connections / resources."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")

    def _clear_credentials(self) -> None:
        """Drop any in-memory credential so the secret becomes GC-able."""
        self._config = None
