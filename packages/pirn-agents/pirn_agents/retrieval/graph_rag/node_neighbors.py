"""``NodeNeighbors`` — expand one frontier node by one hop.

One knot per frontier node, so each ``neighbors`` query has its own ``Result``,
retry, timeout and lineage row rather than being one turn of a Python loop the
run cannot see (Rule 11; PIR-874). Within a hop the queries are independent —
each asks about its own node — so the engine may run them together; it is the
*hops* that depend on each other, which is what the enclosing
:class:`~pirn_agents.retrieval.graph_rag.graph_traversal_loop.GraphTraversalLoop`
is for.

``limit`` is the budget's ``max_fanout``, pushed into the store so the cap is
applied by the query rather than after it.

Internal API. See ``graph_traversal_loop.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.retrieval.graph_stores.graph_neighbor import GraphNeighbor
from pirn_agents.retrieval.graph_stores.graph_store import GraphStore


class NodeNeighbors(Knot):
    """Ask the store for one node's neighbors, bounded by the traversal's fanout."""

    def __init__(
        self,
        *,
        store: Knot | GraphStore,
        node_id: Knot | str,
        direction: Knot | str,
        limit: Knot | int,
        edge_types: Knot | Sequence[str] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            store=store,
            node_id=node_id,
            direction=direction,
            limit=limit,
            edge_types=edge_types,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        store: GraphStore,
        node_id: str,
        direction: str,
        limit: int,
        edge_types: Sequence[str] | None = None,
        **_: Any,
    ) -> tuple[GraphNeighbor, ...]:
        """Return ``node_id``'s neighbors in the given direction.

        Args:
            store: The graph store traversed.
            node_id: The frontier node to expand.
            direction: Neighbor direction to follow.
            limit: The per-node fanout cap.
            edge_types: Optional whitelist of edge types to traverse.

        Returns:
            The neighbors the store returned, in its order.
        """
        found = await store.neighbors(
            node_id,
            direction=direction,
            edge_types=edge_types,
            limit=limit,
        )
        return tuple(found)
