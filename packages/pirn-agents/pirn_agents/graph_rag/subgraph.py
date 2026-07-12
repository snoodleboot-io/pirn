"""``Subgraph`` — a selected set of nodes and the edges among them.

The neutral output of a bounded traversal and the input to a
:class:`~pirn_agents.graph_rag.graph_context_builder.GraphContextBuilder`.
Frozen and opaque; by construction every edge's endpoints are present in
``nodes`` (the traversal never records an edge to a node outside the budget), so
the subgraph is internally consistent.
"""

from __future__ import annotations

from dataclasses import dataclass

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_node import GraphNode


@dataclass(frozen=True)
class Subgraph(PirnOpaqueValue):
    """A consistent node/edge selection produced by a traversal.

    Attributes
    ----------
    nodes:
        The selected nodes.
    edges:
        The edges among the selected nodes.
    """

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]

    def node_ids(self) -> list[str]:
        """Return the ids of the selected nodes, in selection order."""
        return [node.id for node in self.nodes]
