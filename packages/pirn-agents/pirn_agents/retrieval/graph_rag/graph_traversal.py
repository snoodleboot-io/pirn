"""``GraphTraversal`` — bounded k-hop neighborhood queries over a graph.

A :class:`SubTapestry` that expands a seed set into a :class:`Subgraph` by
breadth-first neighborhood traversal, bounded by a
:class:`~pirn_agents.retrieval.graph_rag.traversal_budget.TraversalBudget`
(depth, per-node fanout, total nodes). The ``max_fanout`` bound is pushed into
each :meth:`GraphStore.neighbors` call as its ``limit``, and the ``max_nodes``
bound caps the collected set, so the work is bounded regardless of graph size.
Every recorded edge connects two collected nodes, so the resulting subgraph is
internally consistent.

Shape
-----
The traversal is three things the engine can see, not one opaque ``process()``
(Rule 11; PIR-874):

1. one :class:`~pirn_agents.retrieval.graph_rag.seed_graph_node.SeedGraphNode`
   per seed id — independent reads, count known once ``start_ids`` is resolved;
2. a :class:`~pirn_agents.retrieval.graph_rag.graph_traversal_loop.GraphTraversalLoop`
   hop per depth level — each hop's frontier is the previous hop's discovery, so
   the rounds depend on each other and their number is not known until the run;
3. a :class:`~pirn_agents.retrieval.graph_rag.traversal_subgraph.TraversalSubgraph`
   that narrows the final state to what callers consume.

Every store query is therefore a knot with its own ``Result``, retry, timeout
and lineage row. The version this replaced did all of it inside one
``process()``, so a traversal that made fifty queries recorded one.

The path query moved out
------------------------
``shortest_path`` was a ``@staticmethod`` here carrying a second hand-rolled
BFS. A bounded path query is a query in its own right, not a second way to drive
the traversal knot, so it is now
:class:`~pirn_agents.retrieval.graph_rag.graph_shortest_path.GraphShortestPath`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.retrieval.graph_rag.graph_traversal_loop import GraphTraversalLoop
from pirn_agents.retrieval.graph_rag.seed_graph_node import SeedGraphNode
from pirn_agents.retrieval.graph_rag.seeded_traversal_state import SeededTraversalState
from pirn_agents.retrieval.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.retrieval.graph_rag.traversal_subgraph import TraversalSubgraph
from pirn_agents.retrieval.graph_stores.graph_direction import GraphDirection
from pirn_agents.retrieval.graph_stores.graph_node import GraphNode
from pirn_agents.retrieval.graph_stores.graph_store import GraphStore


class GraphTraversal(SubTapestry):
    """Expand a seed set into a bounded :class:`Subgraph` via BFS neighborhood."""

    #: Inner-graph knot ids (Rule: no module-level constants).
    _seed_prefix: ClassVar[str] = "seed_"
    _seeds_id: ClassVar[str] = "seeds"
    _state_id: ClassVar[str] = "seeded_state"
    _loop_id: ClassVar[str] = "traversal"
    _subgraph_id: ClassVar[str] = "subgraph"

    def __init__(
        self,
        *,
        store: Knot | GraphStore,
        budget: Knot | TraversalBudget,
        _config: KnotConfig,
        direction: Knot | str = GraphDirection.BOTH.value,
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
        direction: str = GraphDirection.BOTH.value,
        edge_types: Sequence[str] | None = None,
        **_: Any,
    ) -> Knot:
        """Declare the traversal and return the knot whose output is the subgraph.

        Args:
            start_ids: The seed node ids to expand from.
            store: The graph store traversed.
            budget: The depth / fanout / size bounds.
            direction: Neighbor direction to follow (see
                :class:`~pirn_agents.retrieval.graph_stores.graph_direction.GraphDirection`).
            edge_types: Optional whitelist of edge types to traverse.

        Returns:
            The sink knot whose output is the collected :class:`Subgraph`.

        Raises:
            ValueError: If ``start_ids`` is empty.
        """
        seeds = list(start_ids)
        if not seeds:
            raise ValueError("GraphTraversal: start_ids must be non-empty")

        store_node = Parameter("store", GraphStore, default=store, _config=KnotConfig(id="store"))
        per_seed: dict[str, Knot] = {
            f"{self._seed_prefix}{index}": SeedGraphNode(
                store=store_node,
                node_id=seed,
                _config=KnotConfig(id=f"{self._seed_prefix}{index}"),
            )
            for index, seed in enumerate(seeds)
        }
        resolved = Aggregator(
            combine=GraphTraversal._in_seed_order,
            _config=KnotConfig(id=type(self)._seeds_id),
            **per_seed,
        )
        seeded = SeededTraversalState(
            store=store_node,
            budget=budget,
            direction=direction,
            seeds=resolved,
            edge_types=edge_types,
            _config=KnotConfig(id=type(self)._state_id),
        )
        # Core owns the hops: one run with one traceable frontier expansion per
        # hop, and one knot per store query inside it (Rule 11; PIR-874).
        traversed = GraphTraversalLoop(
            state=seeded,
            _config=KnotConfig(id=type(self)._loop_id),
        )
        return TraversalSubgraph(state=traversed, _config=KnotConfig(id=type(self)._subgraph_id))

    @staticmethod
    def _in_seed_order(**seeds: GraphNode | None) -> tuple[GraphNode | None, ...]:
        """Put the seed reads back in the order the ids were given.

        The node budget is applied in seed order by
        :class:`SeededTraversalState`, so which seeds it admits must not depend
        on which read finished first.
        """
        ordered = sorted(seeds.items(), key=lambda item: int(item[0].removeprefix("seed_")))
        return tuple(node for _key, node in ordered)
