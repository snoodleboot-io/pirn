"""``TraversalState`` — the value threaded through the breadth-first expansion.

A :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`: it carries the live
:class:`GraphStore` each round queries, which is not describable to pydantic.
Holding it on the loop instead would be graph state shared by every run of the
tapestry (knot-design-rules Rule 4).

Nodes and edges are ordered tuples rather than mappings because the subgraph's
node order is observable (:meth:`Subgraph.node_ids`) and a frozen value should
not hand out a mutable dict. The loop rebuilds dicts for the membership tests
it needs and returns tuples again.

Internal API. See ``graph_traversal_loop.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.retrieval.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.retrieval.graph_stores.graph_edge import GraphEdge
from pirn_agents.retrieval.graph_stores.graph_node import GraphNode
from pirn_agents.retrieval.graph_stores.graph_store import GraphStore


@dataclass(frozen=True)
class TraversalState(PirnOpaqueValue):
    """One hop's worth of accumulated traversal state.

    Frozen; the loop returns a new instance rather than mutating.

    Attributes:
        store: The graph store each round queries.
        budget: The depth / fanout / size bounds.
        direction: Neighbor direction to follow.
        edge_types: Optional whitelist of edge types to traverse.
        nodes: Every node collected so far, in collection order.
        edges: Every edge recorded so far, in record order.
        frontier: The node ids this round expands.
        rounds_left: How many hops the budget still allows.
    """

    store: GraphStore
    budget: TraversalBudget
    direction: str
    edge_types: tuple[str, ...] | None
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    frontier: tuple[str, ...]
    rounds_left: int

    def with_fields(self, **changes: Any) -> TraversalState:
        """Return a copy with ``changes`` applied."""
        return replace(self, **changes)

    def edge_type_filter(self) -> Sequence[str] | None:
        """Return ``edge_types`` in the form ``GraphStore.neighbors`` expects."""
        return self.edge_types

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return the lineage-relevant fields, leaving the live store out."""
        return {
            "direction": self.direction,
            "edge_types": list(self.edge_types) if self.edge_types is not None else None,
            "max_depth": self.budget.max_depth,
            "max_fanout": self.budget.max_fanout,
            "max_nodes": self.budget.max_nodes,
            "nodes_collected": len(self.nodes),
            "edges_collected": len(self.edges),
            "frontier_size": len(self.frontier),
            "rounds_left": self.rounds_left,
        }
