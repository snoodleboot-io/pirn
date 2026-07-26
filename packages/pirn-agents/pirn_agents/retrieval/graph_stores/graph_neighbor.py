"""``GraphNeighbor`` — one (edge, node) pair returned by a neighborhood step.

The neutral read unit every
:class:`~pirn_agents.retrieval.graph_stores.graph_store.GraphStore` returns from
:meth:`~pirn_agents.retrieval.graph_stores.graph_store.GraphStore.neighbors`: the traversed
``edge`` together with the ``node`` reached across it. Frozen and opaque.
"""

from __future__ import annotations

from dataclasses import dataclass

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.retrieval.graph_stores.graph_edge import GraphEdge
from pirn_agents.retrieval.graph_stores.graph_node import GraphNode


@dataclass(frozen=True)
class GraphNeighbor(PirnOpaqueValue):
    """A single neighborhood hit: the ``edge`` traversed and the ``node`` reached.

    Attributes
    ----------
    edge:
        The relationship traversed to reach ``node``.
    node:
        The adjacent node reached across ``edge``.
    """

    edge: GraphEdge
    node: GraphNode

    def __post_init__(self) -> None:
        if not isinstance(self.edge, GraphEdge):
            raise TypeError(
                f"GraphNeighbor: edge must be a GraphEdge, got {type(self.edge).__name__}"
            )
        if not isinstance(self.node, GraphNode):
            raise TypeError(
                f"GraphNeighbor: node must be a GraphNode, got {type(self.node).__name__}"
            )
