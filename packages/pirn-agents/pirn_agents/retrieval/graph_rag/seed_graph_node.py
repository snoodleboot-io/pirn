"""``SeedGraphNode`` — fetch one seed node, or report that it is not there.

One knot per seed id, so each ``get_node`` has its own ``Result``, retry,
timeout and lineage row rather than being one turn of a Python loop the run
cannot see (Rule 11; PIR-874). The reads are independent, so the engine may
run them together.

A seed id with no node behind it yields ``None``: a traversal has always
skipped an unknown seed rather than failing for it, and ``Skipped`` would
propagate to the knot that assembles the initial state.

Internal API. See ``graph_traversal.py``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.retrieval.graph_stores.graph_node import GraphNode
from pirn_agents.retrieval.graph_stores.graph_store import GraphStore


class SeedGraphNode(Knot):
    """Read one seed node out of the graph store."""

    def __init__(
        self,
        *,
        store: Knot | GraphStore,
        node_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(store=store, node_id=node_id, _config=_config, **kwargs)

    async def process(self, store: GraphStore, node_id: str, **_: Any) -> GraphNode | None:
        """Return the node stored under ``node_id``, or ``None``.

        Args:
            store: The graph store to read from.
            node_id: The seed id to resolve.

        Returns:
            The node, or ``None`` when the store has no such node.
        """
        return await store.get_node(node_id)
