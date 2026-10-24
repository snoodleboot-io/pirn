"""``GraphShortestPath`` — bounded shortest-path query between two graph nodes.

A :class:`SubTapestry` that answers "the fewest hops from ``source_id`` to
``target_id``, within ``max_depth`` hops and ``max_fanout`` neighbors per node",
or ``None`` when no such path exists inside the budget. Breadth-first, so the
first path found is a shortest one.

This was a ``@staticmethod`` on
:class:`~pirn_agents.retrieval.graph_rag.graph_traversal.GraphTraversal` whose
body was a hand-rolled ``for depth: for path: await store.neighbors(...)`` — a
whole bounded search the run saw nothing of, and which no graph could schedule,
retry, time out or replay. It is a knot of its own now because it is a query in
its own right, not a second way to drive the traversal knot (PIR-874).

Shape
-----
1. a :class:`~pirn_agents.retrieval.graph_rag.shortest_path_loop.ShortestPathLoop`
   hop per depth level — each hop extends the paths the previous hop produced,
   so the rounds depend on each other and their number is not known until the
   run;
2. inside each hop, one
   :class:`~pirn_agents.retrieval.graph_rag.node_neighbors.NodeNeighbors` knot
   per frontier path — independent queries the engine runs together;
3. a :class:`~pirn_agents.retrieval.graph_rag.shortest_path_result.ShortestPathResult`
   that narrows the final state to the path.

``source_id == target_id`` needs no query at all, so the seeded state already
carries the answer and the loop ends without a hop.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.retrieval.graph_rag.path_search_state import PathSearchState
from pirn_agents.retrieval.graph_rag.shortest_path_loop import ShortestPathLoop
from pirn_agents.retrieval.graph_rag.shortest_path_result import ShortestPathResult
from pirn_agents.retrieval.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.retrieval.graph_stores.graph_direction import GraphDirection
from pirn_agents.retrieval.graph_stores.graph_store import GraphStore


class GraphShortestPath(SubTapestry):
    """Find the shortest node-id path between two nodes, within a traversal budget."""

    #: Inner-graph knot ids (Rule: no module-level constants).
    _loop_id: ClassVar[str] = "path_search"
    _result_id: ClassVar[str] = "path"

    def __init__(
        self,
        *,
        source_id: Knot | str,
        target_id: Knot | str,
        store: Knot | GraphStore,
        budget: Knot | TraversalBudget,
        _config: KnotConfig,
        direction: Knot | str = GraphDirection.BOTH.value,
        edge_types: Knot | Sequence[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_id=source_id,
            target_id=target_id,
            store=store,
            budget=budget,
            direction=direction,
            edge_types=edge_types,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        source_id: str,
        target_id: str,
        store: GraphStore,
        budget: TraversalBudget,
        direction: str = GraphDirection.BOTH.value,
        edge_types: Sequence[str] | None = None,
        **_: Any,
    ) -> Knot:
        """Declare the search and return the knot whose output is the path.

        Args:
            source_id: The path's start node id.
            target_id: The path's end node id.
            store: The graph store traversed.
            budget: The depth / fanout bounds applied to the search.
            direction: Neighbor direction to follow.
            edge_types: Optional whitelist of edge types to traverse.

        Returns:
            The sink knot whose output is the node-id path inclusive of both
            endpoints, or ``None`` when no path exists within the budget.
        """
        reached = source_id == target_id
        seeded = PathSearchState(
            store=store,
            budget=budget,
            direction=direction,
            edge_types=tuple(edge_types) if edge_types is not None else None,
            target_id=target_id,
            visited=(source_id,),
            frontier=() if reached else ((source_id,),),
            found=(source_id,) if reached else None,
            rounds_left=budget.max_depth,
        )
        searched = ShortestPathLoop(
            state=seeded,
            _config=KnotConfig(id=type(self)._loop_id),
        )
        return ShortestPathResult(state=searched, _config=KnotConfig(id=type(self)._result_id))
