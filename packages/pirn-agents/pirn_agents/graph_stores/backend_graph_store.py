"""``BackendGraphStore`` — shared :class:`GraphStore` over a neutral backend client.

Both the Neo4j and Kuzu adapters share identical value translation
(:class:`GraphNode` / :class:`GraphEdge` ↔ neutral mappings) and differ only in
which :class:`~pirn_agents.graph_stores.graph_backend_client.GraphBackendClient`
they lazily build. This base holds that translation and delegates every
graph-native method to the client; concrete adapters override
:meth:`_create_client` to build their vendor wrapper behind a lazy import. A
pre-built client may be injected (the test seam), so mirrored tests run the full
conformance suite against an in-memory fake with no backend installed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.credential_ref import CredentialRef
from pirn_agents.graph_stores.graph_backend_client import GraphBackendClient
from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_neighbor import GraphNeighbor
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.graph_stores.graph_store import GraphStore


class BackendGraphStore(GraphStore):
    """Abstract :class:`GraphStore` speaking the neutral graph backend client."""

    def __init__(
        self,
        *,
        credential: CredentialRef | None = None,
        client: GraphBackendClient | None = None,
    ) -> None:
        """Initialise the adapter without importing any backend.

        Args:
            credential: Optional credential scrubbed on :meth:`close`.
            client: Optional pre-built neutral backend client (the test seam);
                when supplied no backend import happens.
        """
        self._credential: CredentialRef | None = credential
        self._client: GraphBackendClient | None = client

    async def _create_client(self) -> GraphBackendClient:
        """Build the vendor backend client. Overridden by concrete adapters.

        Raises:
            NotImplementedError: Always, in the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _create_client()")

    async def _get_client(self) -> GraphBackendClient:
        """Return the backend client, lazily building the real one once."""
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def upsert_nodes(self, nodes: Sequence[GraphNode]) -> None:
        """Upsert ``nodes`` through the neutral backend client."""
        payload = [
            {"id": node.id, "type": node.type, "properties": dict(node.properties)}
            for node in nodes
        ]
        if not payload:
            return
        client = await self._get_client()
        await client.upsert_nodes(payload)

    async def upsert_edges(self, edges: Sequence[GraphEdge]) -> None:
        """Upsert ``edges`` through the neutral backend client."""
        payload = [
            {
                "id": edge.id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "type": edge.type,
                "properties": dict(edge.properties),
            }
            for edge in edges
        ]
        if not payload:
            return
        client = await self._get_client()
        await client.upsert_edges(payload)

    async def get_node(self, node_id: str) -> GraphNode | None:
        """Return the node stored under ``node_id``, or ``None``."""
        client = await self._get_client()
        node = await client.get_node(node_id)
        return self._to_node(node) if node is not None else None

    async def get_edge(self, edge_id: str) -> GraphEdge | None:
        """Return the edge stored under ``edge_id``, or ``None``."""
        client = await self._get_client()
        edge = await client.get_edge(edge_id)
        return self._to_edge(edge) if edge is not None else None

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
                f"{type(self).__name__}: direction must be 'out'|'in'|'both', got {direction!r}"
            )
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ValueError(f"{type(self).__name__}: limit must be a positive int, got {limit!r}")
        client = await self._get_client()
        hits = await client.neighbors(
            node_id, direction=direction, edge_types=edge_types, limit=limit
        )
        return [
            GraphNeighbor(edge=self._to_edge(hit["edge"]), node=self._to_node(hit["node"]))
            for hit in hits
        ]

    async def query(
        self,
        *,
        node_type: str | None = None,
        properties: Mapping[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[GraphNode]:
        """Return nodes matching ``node_type`` and every ``properties`` entry."""
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ValueError(f"{type(self).__name__}: limit must be a positive int, got {limit!r}")
        client = await self._get_client()
        nodes = await client.query_nodes(node_type=node_type, properties=properties, limit=limit)
        return [self._to_node(node) for node in nodes]

    async def delete_nodes(self, ids: Sequence[str]) -> None:
        """Remove each node in ``ids`` along with its incident edges."""
        if not ids:
            return
        client = await self._get_client()
        await client.delete_nodes(list(ids))

    async def delete_edges(self, ids: Sequence[str]) -> None:
        """Remove each edge in ``ids``."""
        if not ids:
            return
        client = await self._get_client()
        await client.delete_edges(list(ids))

    async def close(self) -> None:
        """Close the backend client and scrub credentials."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        self._clear_credentials()

    def _clear_credentials(self) -> None:
        """Drop the credential so the secret becomes GC-able."""
        self._credential = None

    @staticmethod
    def _to_node(node: Mapping[str, Any]) -> GraphNode:
        """Translate a neutral node mapping into a :class:`GraphNode`."""
        return GraphNode.create(
            id=node["id"], type=node["type"], properties=dict(node.get("properties", {}))
        )

    @staticmethod
    def _to_edge(edge: Mapping[str, Any]) -> GraphEdge:
        """Translate a neutral edge mapping into a :class:`GraphEdge`."""
        return GraphEdge.create(
            id=edge["id"],
            source_id=edge["source_id"],
            target_id=edge["target_id"],
            type=edge["type"],
            properties=dict(edge.get("properties", {})),
        )
