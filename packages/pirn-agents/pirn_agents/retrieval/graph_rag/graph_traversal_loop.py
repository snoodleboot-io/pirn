"""``GraphTraversalLoop`` — one breadth-first hop per iteration.

Each hop's frontier is whatever the previous hop discovered, and how many hops
run depends on the budget and on when the frontier empties. The shape is
unknown until the run, which is what ``LoopSubTapestry`` is for
(knot-design-rules Rule 11) — unlike a chain or a fan-out, whose shape is fixed
when the graph is built.

Within a hop the per-node ``neighbors`` queries are independent, so they are a
fan-out of :class:`~pirn_agents.retrieval.graph_rag.node_neighbors.NodeNeighbors`
knots the engine runs together. It replaces a nested ``for depth: for node_id:
await store.neighbors(...)`` that gave the whole traversal one lineage row, one
``Result``, one retry budget and one timeout however many queries it made
(PIR-874).

Why the fold applies a hop's results in frontier order
------------------------------------------------------
``max_nodes`` is a *running* cap, so which neighbors are admitted depends on the
order they are considered. The queries now run concurrently, but :meth:`fold`
walks the frontier in its original order and reads each node's neighbors from
the aggregator — so the subgraph is identical to the sequential loop's, and does
not depend on which query finished first.

Internal API. See ``graph_traversal.py``.
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
from pirn_agents.retrieval.graph_rag.traversal_state import TraversalState
from pirn_agents.retrieval.graph_stores.graph_edge import GraphEdge
from pirn_agents.retrieval.graph_stores.graph_neighbor import GraphNeighbor
from pirn_agents.retrieval.graph_stores.graph_node import GraphNode
from pirn_agents.retrieval.graph_stores.graph_store import GraphStore


class GraphTraversalLoop(LoopSubTapestry[TraversalState]):
    """Expand the whole frontier each hop until the depth budget or the graph ends."""

    #: Per-iteration knot ids (Rule: no module-level constants).
    _expansion_prefix: ClassVar[str] = "expand_"
    _hop_id: ClassVar[str] = "hop"

    def step(self, state: TraversalState) -> tuple[Tapestry, TraversalState] | None:
        """Build this hop's fan-out, or ``None`` once the traversal is over.

        Reads only: :meth:`fold` owns every change to the accumulated state.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The hop's tapestry paired with ``state``, or ``None`` when the
            frontier is empty or the depth budget is spent.
        """
        if not state.frontier or state.rounds_left <= 0:
            return None
        with Tapestry() as hop:
            store_node = Parameter(
                "store", GraphStore, default=state.store, _config=KnotConfig(id="store")
            )
            per_node: dict[str, Knot] = {
                f"{self._expansion_prefix}{index}": NodeNeighbors(
                    store=store_node,
                    node_id=node_id,
                    direction=state.direction,
                    limit=state.budget.max_fanout,
                    edge_types=state.edge_type_filter(),
                    _config=KnotConfig(id=f"{self._expansion_prefix}{index}"),
                )
                for index, node_id in enumerate(state.frontier)
            }
            Aggregator(
                combine=GraphTraversalLoop._by_frontier_position,
                _config=KnotConfig(id=type(self)._hop_id),
                **per_node,
            )
        return hop, state

    def fold(self, state: TraversalState, result: RunResult) -> TraversalState:
        """Collect the hop's neighbors and open the next frontier.

        Walks the frontier in its original order so the running ``max_nodes``
        cap admits exactly the nodes the sequential loop admitted.

        Args:
            state: State as ``step`` returned it.
            result: The hop's run result, whose aggregator output is one
                neighbor tuple per frontier position.

        Returns:
            A state with the new nodes and edges collected, the next frontier
            set, and one hop deducted.
        """
        by_position: Any = result.outputs[type(self)._hop_id]
        nodes: dict[str, GraphNode] = {node.id: node for node in state.nodes}
        edges: dict[str, GraphEdge] = {edge.id: edge for edge in state.edges}
        next_frontier: list[str] = []
        for position in range(len(state.frontier)):
            neighbors: tuple[GraphNeighbor, ...] = by_position[position]
            for neighbor in neighbors:
                if neighbor.node.id not in nodes and len(nodes) < state.budget.max_nodes:
                    nodes[neighbor.node.id] = neighbor.node
                    next_frontier.append(neighbor.node.id)
                if neighbor.node.id in nodes:
                    edges[neighbor.edge.id] = neighbor.edge
        return state.with_fields(
            nodes=tuple(nodes.values()),
            edges=tuple(edges.values()),
            frontier=tuple(next_frontier),
            rounds_left=state.rounds_left - 1,
        )

    def step_id(self, state: TraversalState, idx: int) -> str:
        """Name each hop for run history."""
        return f"hop_{idx}"

    @staticmethod
    def _by_frontier_position(
        **expansions: tuple[GraphNeighbor, ...],
    ) -> tuple[tuple[GraphNeighbor, ...], ...]:
        """Put each node's neighbors back at its position in the frontier.

        Keys are ``expand_<index>``; sorting on the index rather than on the
        mapping's order is what makes the running node cap independent of
        scheduling.
        """
        ordered = sorted(expansions.items(), key=lambda item: int(item[0].removeprefix("expand_")))
        return tuple(neighbors for _key, neighbors in ordered)
