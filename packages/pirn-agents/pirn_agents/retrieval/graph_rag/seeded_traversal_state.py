"""``SeededTraversalState`` — turn the resolved seed nodes into the loop's first state.

The seed reads fan out, so the state the loop starts from cannot be built until
they have all landed. This knot is where they land: it applies the node budget
in seed order — exactly where the ``for seed in seeds`` loop it replaced applied
it — and hands the loop a frontier.

Internal API. See ``graph_traversal.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.retrieval.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.retrieval.graph_rag.traversal_state import TraversalState
from pirn_agents.retrieval.graph_stores.graph_node import GraphNode
from pirn_agents.retrieval.graph_stores.graph_store import GraphStore


class SeededTraversalState(Knot):
    """Collect the seed nodes the budget allows and open the first frontier."""

    def __init__(
        self,
        *,
        store: Knot | GraphStore,
        budget: Knot | TraversalBudget,
        direction: Knot | str,
        seeds: Knot | Sequence[GraphNode | None],
        edge_types: Knot | Sequence[str] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            store=store,
            budget=budget,
            direction=direction,
            seeds=seeds,
            edge_types=edge_types,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        store: GraphStore,
        budget: TraversalBudget,
        direction: str,
        seeds: Sequence[GraphNode | None],
        edge_types: Sequence[str] | None = None,
        **_: Any,
    ) -> TraversalState:
        """Build the state the first hop expands from.

        Args:
            store: The graph store the traversal queries.
            budget: The depth / fanout / size bounds.
            direction: Neighbor direction to follow.
            seeds: One entry per requested seed id, ``None`` where the store had
                no such node, in the order the ids were given.
            edge_types: Optional whitelist of edge types to traverse.

        Returns:
            The initial :class:`TraversalState`: the seeds the node budget
            admits, no edges yet, and those seeds as the frontier.
        """
        collected: dict[str, GraphNode] = {}
        for node in seeds:
            if node is None:
                continue
            if len(collected) >= budget.max_nodes:
                break
            collected[node.id] = node
        return TraversalState(
            store=store,
            budget=budget,
            direction=direction,
            edge_types=tuple(edge_types) if edge_types is not None else None,
            nodes=tuple(collected.values()),
            edges=(),
            frontier=tuple(collected),
            rounds_left=budget.max_depth,
        )
