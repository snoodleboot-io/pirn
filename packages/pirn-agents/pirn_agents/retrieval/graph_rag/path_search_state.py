"""``PathSearchState`` — the value threaded through the bounded path search.

A :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`: it carries the live
:class:`GraphStore` each hop queries, which is not describable to pydantic.
Holding it on the loop instead would be graph state shared by every run of the
tapestry (knot-design-rules Rule 4).

Internal API. See ``shortest_path_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.retrieval.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.retrieval.graph_stores.graph_store import GraphStore


@dataclass(frozen=True)
class PathSearchState(PirnOpaqueValue):
    """One hop's worth of accumulated path-search state.

    Frozen; the loop returns a new instance rather than mutating.

    Attributes:
        store: The graph store each hop queries.
        budget: The depth / fanout bounds applied to the search.
        direction: Neighbor direction to follow.
        edge_types: Optional whitelist of edge types to traverse.
        target_id: The node the search is trying to reach.
        visited: Every node id already reached, so a node is queued once.
        frontier: The paths this hop extends, each a node-id sequence from the
            source.
        found: The completed path once the target is reached, else ``None``.
        rounds_left: How many hops the budget still allows.
    """

    store: GraphStore
    budget: TraversalBudget
    direction: str
    edge_types: tuple[str, ...] | None
    target_id: str
    visited: tuple[str, ...]
    frontier: tuple[tuple[str, ...], ...]
    found: tuple[str, ...] | None
    rounds_left: int

    def with_fields(self, **changes: Any) -> PathSearchState:
        """Return a copy with ``changes`` applied."""
        return replace(self, **changes)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return the lineage-relevant fields, leaving the live store out."""
        return {
            "direction": self.direction,
            "edge_types": list(self.edge_types) if self.edge_types is not None else None,
            "max_depth": self.budget.max_depth,
            "max_fanout": self.budget.max_fanout,
            "target_id": self.target_id,
            "visited": len(self.visited),
            "frontier_size": len(self.frontier),
            "found": list(self.found) if self.found is not None else None,
            "rounds_left": self.rounds_left,
        }
