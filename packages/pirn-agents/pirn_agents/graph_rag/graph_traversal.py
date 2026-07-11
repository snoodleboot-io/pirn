"""``GraphTraversal`` — bounded k-hop neighborhood + path queries over a graph.

A :class:`Knot` that expands a seed set into a :class:`Subgraph` by breadth-first
neighborhood traversal, bounded by a
:class:`~pirn_agents.graph_rag.traversal_budget.TraversalBudget` (depth, per-node
fanout, total nodes). The ``max_fanout`` bound is pushed into each
:meth:`GraphStore.neighbors` call as its ``limit``, and the ``max_nodes`` bound
caps the collected set, so the work is bounded regardless of graph size. Every
recorded edge connects two collected nodes, so the resulting subgraph is
internally consistent.

Alongside the ``process`` neighborhood expansion, :meth:`shortest_path` answers a
bounded path query between two nodes (shortest hop count within ``max_depth``).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.graph_rag.subgraph import Subgraph
from pirn_agents.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.graph_stores.graph_store import GraphStore


class GraphTraversal(Knot):
    """Expand a seed set into a bounded :class:`Subgraph` via BFS neighborhood."""

    def __init__(
        self,
        *,
        store: Knot | GraphStore,
        budget: Knot | TraversalBudget,
        _config: KnotConfig,
        direction: Knot | str = "both",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            store=store,
            budget=budget,
            direction=direction,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        start_ids: Sequence[str],
        store: GraphStore,
        budget: TraversalBudget,
        direction: str = "both",
        edge_types: Sequence[str] | None = None,
        **_: Any,
    ) -> Subgraph:
        """Expand ``start_ids`` into a bounded :class:`Subgraph`.

        Args:
            start_ids: The seed node ids to expand from.
            store: The graph store traversed.
            budget: The depth / fanout / size bounds.
            direction: Neighbor direction to follow (``"out"``/``"in"``/``"both"``).
            edge_types: Optional whitelist of edge types to traverse.

        Returns:
            The collected :class:`Subgraph` (nodes + internal edges).

        Raises:
            TypeError: If ``store`` is not a :class:`GraphStore` or ``budget`` is
                not a :class:`TraversalBudget`.
            ValueError: If ``start_ids`` is empty.
        """
        if not isinstance(store, GraphStore):
            raise TypeError(
                f"GraphTraversal: store must be a GraphStore, got {type(store).__name__}"
            )
        if not isinstance(budget, TraversalBudget):
            raise TypeError(
                f"GraphTraversal: budget must be a TraversalBudget, got {type(budget).__name__}"
            )
        seeds = list(start_ids)
        if not seeds:
            raise ValueError("GraphTraversal: start_ids must be non-empty")

        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}
        for seed in seeds:
            node = await store.get_node(seed)
            if node is not None and len(nodes) < budget.max_nodes:
                nodes[seed] = node

        frontier = list(nodes)
        for _depth in range(budget.max_depth):
            next_frontier: list[str] = []
            for node_id in frontier:
                neighbors = await store.neighbors(
                    node_id,
                    direction=direction,
                    edge_types=edge_types,
                    limit=budget.max_fanout,
                )
                for neighbor in neighbors:
                    if neighbor.node.id not in nodes and len(nodes) < budget.max_nodes:
                        nodes[neighbor.node.id] = neighbor.node
                        next_frontier.append(neighbor.node.id)
                    if neighbor.node.id in nodes:
                        edges[neighbor.edge.id] = neighbor.edge
            frontier = next_frontier
            if not frontier:
                break

        return Subgraph(nodes=tuple(nodes.values()), edges=tuple(edges.values()))

    async def shortest_path(
        self,
        source_id: str,
        target_id: str,
        store: GraphStore,
        budget: TraversalBudget,
        direction: str = "both",
        edge_types: Sequence[str] | None = None,
    ) -> list[str] | None:
        """Return the shortest node-id path from ``source_id`` to ``target_id``.

        A bounded breadth-first path query: it explores at most ``max_depth`` hops
        with ``max_fanout`` neighbors per node and returns the first (hence
        shortest) path found, or ``None`` if none exists within the budget.

        Args:
            source_id: The path's start node id.
            target_id: The path's end node id.
            store: The graph store traversed.
            budget: The depth / fanout bounds applied to the search.
            direction: Neighbor direction to follow.
            edge_types: Optional whitelist of edge types to traverse.

        Returns:
            The node-id path inclusive of both endpoints, or ``None``.
        """
        if source_id == target_id:
            return [source_id]
        visited: set[str] = {source_id}
        frontier: list[list[str]] = [[source_id]]
        for _depth in range(budget.max_depth):
            next_frontier: list[list[str]] = []
            for path in frontier:
                neighbors = await store.neighbors(
                    path[-1], direction=direction, edge_types=edge_types, limit=budget.max_fanout
                )
                for neighbor in neighbors:
                    reached = neighbor.node.id
                    if reached == target_id:
                        return [*path, reached]
                    if reached not in visited:
                        visited.add(reached)
                        next_frontier.append([*path, reached])
            frontier = next_frontier
            if not frontier:
                break
        return None
