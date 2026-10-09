"""``ShortestPathLoop`` — one hop of the bounded shortest-path search per iteration.

Breadth-first, so the first time the target is reached it is reached by a
shortest path. Each hop extends the paths the previous hop produced, and how
many hops run depends on the depth budget and on when the target is found or
the frontier empties — a shape unknown until the run, which is what
``LoopSubTapestry`` is for (knot-design-rules Rule 11).

Within a hop the per-path ``neighbors`` queries are independent, so they are a
fan-out of :class:`~pirn_agents.retrieval.graph_rag.node_neighbors.NodeNeighbors`
knots the engine runs together. It replaces a nested ``for depth: for path:
await store.neighbors(...)`` that recorded one lineage row for the whole search
(PIR-874).

Why the fold applies a hop's results in frontier order
------------------------------------------------------
The search it replaced returned the *first* path that reached the target,
scanning the frontier in order and each node's neighbors in the store's order.
:meth:`fold` walks the frontier in that same order and stops at the first hit,
so the path returned is the one the sequential search returned and does not
depend on which query finished first.

Internal API. See ``graph_shortest_path.py``.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_result import RunResult
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.retrieval.graph_rag.node_neighbors import NodeNeighbors
from pirn_agents.retrieval.graph_rag.path_search_state import PathSearchState
from pirn_agents.retrieval.graph_stores.graph_neighbor import GraphNeighbor
from pirn_agents.retrieval.graph_stores.graph_store import GraphStore


class ShortestPathLoop(LoopSubTapestry[PathSearchState]):
    """Extend every frontier path by one hop until the target, the budget, or the graph ends."""

    #: Per-iteration knot ids (Rule: no module-level constants).
    _extension_prefix: ClassVar[str] = "extend_"
    _hop_id: ClassVar[str] = "hop"

    def step(self, state: PathSearchState) -> tuple[Tapestry, PathSearchState] | None:
        """Build this hop's fan-out, or ``None`` once the search is over.

        Reads only: :meth:`fold` owns every change to the accumulated state.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The hop's tapestry paired with ``state``, or ``None`` once the
            target is found, the frontier is empty, or the depth budget is spent.
        """
        if state.found is not None or not state.frontier or state.rounds_left <= 0:
            return None
        with Tapestry() as hop:
            store_node = Parameter(
                "store", GraphStore, default=state.store, _config=KnotConfig(id="store")
            )
            per_path: dict[str, Knot] = {
                f"{self._extension_prefix}{index}": NodeNeighbors(
                    store=store_node,
                    node_id=path[-1],
                    direction=state.direction,
                    limit=state.budget.max_fanout,
                    edge_types=state.edge_types,
                    _config=KnotConfig(id=f"{self._extension_prefix}{index}"),
                )
                for index, path in enumerate(state.frontier)
            }
            Aggregator(
                combine=ShortestPathLoop._by_frontier_position,
                _config=KnotConfig(id=type(self)._hop_id),
                **per_path,
            )
        return hop, state

    def fold(self, state: PathSearchState, result: RunResult) -> PathSearchState:
        """Record the first path that reached the target, or open the next frontier.

        Args:
            state: State as ``step`` returned it.
            result: The hop's run result, whose aggregator output is one
                neighbor tuple per frontier position.

        Returns:
            A state carrying the found path, or the extended frontier with one
            hop deducted.
        """
        by_position: Any = result.outputs[type(self)._hop_id]
        visited = set(state.visited)
        ordered_visited = list(state.visited)
        next_frontier: list[tuple[str, ...]] = []
        for position, path in enumerate(state.frontier):
            neighbors: tuple[GraphNeighbor, ...] = by_position[position]
            for neighbor in neighbors:
                reached = neighbor.node.id
                if reached == state.target_id:
                    return state.with_fields(
                        found=(*path, reached),
                        frontier=(),
                        rounds_left=state.rounds_left - 1,
                    )
                if reached not in visited:
                    visited.add(reached)
                    ordered_visited.append(reached)
                    next_frontier.append((*path, reached))
        return state.with_fields(
            visited=tuple(ordered_visited),
            frontier=tuple(next_frontier),
            rounds_left=state.rounds_left - 1,
        )

    def step_id(self, state: PathSearchState, idx: int) -> str:
        """Name each hop for run history."""
        return f"hop_{idx}"

    @staticmethod
    def _by_frontier_position(
        **extensions: tuple[GraphNeighbor, ...],
    ) -> tuple[tuple[GraphNeighbor, ...], ...]:
        """Put each path's neighbors back at its position in the frontier.

        Keys are ``extend_<index>``; sorting on the index rather than on the
        mapping's order is what makes "the first path that reaches the target"
        independent of scheduling.
        """
        ordered = sorted(extensions.items(), key=lambda item: int(item[0].removeprefix("extend_")))
        return tuple(neighbors for _key, neighbors in ordered)
