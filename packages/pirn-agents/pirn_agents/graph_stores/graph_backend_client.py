"""``GraphBackendClient`` — the neutral async surface external graph stores talk to.

Neo4j and Kuzu expose very different drivers, so their
:class:`~pirn_agents.graph_stores.graph_store.GraphStore` adapters do not call
those drivers directly. Instead each adapter depends on this provider-neutral
base class and a thin backend wrapper implements it by lazily importing and
translating to the vendor driver. That seam keeps the adapters vendor-agnostic
and lets mirrored tests inject an in-memory fake client that runs the full
conformance suite with no backend installed.

The base class raises :class:`NotImplementedError` for every method (the house
interface style — never :class:`typing.Protocol`) and is opaque
(:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`) because a concrete client
holds live vendor state (driver, credential): it drops into the pirn graph as a
config value by ``isinstance`` without descending into the content-addressed
hash. Model on the sibling :class:`~pirn_agents.graph_stores.graph_store.GraphStore`.

Nodes, edges, and neighbors are plain mappings:

* node     — ``{"id", "type", "properties"}``;
* edge     — ``{"id", "source_id", "target_id", "type", "properties"}``;
* neighbor — ``{"edge": <edge>, "node": <node>}``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class GraphBackendClient(PirnOpaqueValue):
    """Abstract neutral async client every external graph backend is wrapped into."""

    async def upsert_nodes(self, nodes: Sequence[Mapping[str, Any]]) -> None:
        """Insert or overwrite each node mapping by its ``id``."""
        raise NotImplementedError(f"{type(self).__name__} must implement upsert_nodes()")

    async def upsert_edges(self, edges: Sequence[Mapping[str, Any]]) -> None:
        """Insert or overwrite each edge mapping by its ``id``."""
        raise NotImplementedError(f"{type(self).__name__} must implement upsert_edges()")

    async def get_node(self, node_id: str) -> Mapping[str, Any] | None:
        """Return the node mapping stored under ``node_id``, or ``None``."""
        raise NotImplementedError(f"{type(self).__name__} must implement get_node()")

    async def get_edge(self, edge_id: str) -> Mapping[str, Any] | None:
        """Return the edge mapping stored under ``edge_id``, or ``None``."""
        raise NotImplementedError(f"{type(self).__name__} must implement get_edge()")

    async def neighbors(
        self,
        node_id: str,
        *,
        direction: str,
        edge_types: Sequence[str] | None,
        limit: int | None,
    ) -> list[Mapping[str, Any]]:
        """Return the one-hop neighbor mappings of ``node_id``."""
        raise NotImplementedError(f"{type(self).__name__} must implement neighbors()")

    async def query_nodes(
        self,
        *,
        node_type: str | None,
        properties: Mapping[str, Any] | None,
        limit: int | None,
    ) -> list[Mapping[str, Any]]:
        """Return node mappings matching ``node_type`` and every ``properties`` entry."""
        raise NotImplementedError(f"{type(self).__name__} must implement query_nodes()")

    async def delete_nodes(self, ids: Sequence[str]) -> None:
        """Remove every node whose id is in ``ids`` and its incident edges."""
        raise NotImplementedError(f"{type(self).__name__} must implement delete_nodes()")

    async def delete_edges(self, ids: Sequence[str]) -> None:
        """Remove every edge whose id is in ``ids``."""
        raise NotImplementedError(f"{type(self).__name__} must implement delete_edges()")

    async def close(self) -> None:
        """Release the underlying backend driver."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")
