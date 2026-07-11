"""``SubGraphContextBuilder`` — render a :class:`Subgraph` into RAG context.

A :class:`Knot` that turns a selected subgraph (produced by
:class:`~pirn_agents.graph_rag.graph_traversal.GraphTraversal` or the hybrid
retriever) into agent-consumable context: a deterministic, human-readable
listing of the entities and their relations, wrapped in an
:class:`~pirn_agents.types.agent_message.AgentMessage` so it drops straight into
a prompt as grounding for GraphRAG. Nodes and edges are sorted by id so the
rendered context is stable across runs (cache-friendly).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.graph_rag.subgraph import Subgraph
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.types.agent_message import AgentMessage


class SubGraphContextBuilder(Knot):
    """Render a :class:`Subgraph` into a list of context :class:`AgentMessage`."""

    def __init__(
        self,
        *,
        _config: KnotConfig,
        role: Knot | str = "system",
        name: Knot | str = "graph_context",
        **kwargs: Any,
    ) -> None:
        super().__init__(role=role, name=name, _config=_config, **kwargs)

    async def process(
        self,
        subgraph: Subgraph,
        role: str = "system",
        name: str = "graph_context",
        **_: Any,
    ) -> list[AgentMessage]:
        """Render ``subgraph`` into a single-element list of context messages.

        Args:
            subgraph: The selected subgraph to render.
            role: The role of the emitted message (e.g. ``"system"``).
            name: The message ``name`` tagging it as graph context.

        Returns:
            A one-element list holding the rendered context
            :class:`AgentMessage`.

        Raises:
            TypeError: If ``subgraph`` is not a :class:`Subgraph`.
        """
        if not isinstance(subgraph, Subgraph):
            raise TypeError(
                f"SubGraphContextBuilder: subgraph must be a Subgraph, "
                f"got {type(subgraph).__name__}"
            )
        content = self._render(subgraph)
        return [AgentMessage(role=role, content=content, name=name)]

    @staticmethod
    def _render(subgraph: Subgraph) -> str:
        """Render the subgraph as a stable entities-and-relations listing."""
        nodes = sorted(subgraph.nodes, key=lambda node: node.id)
        edges = sorted(subgraph.edges, key=lambda edge: edge.id)
        lines: list[str] = ["Knowledge graph context:", "Entities:"]
        if nodes:
            for node in nodes:
                lines.append(f"- {node.id} ({node.type}){SubGraphContextBuilder._props(node)}")
        else:
            lines.append("- (none)")
        lines.append("Relations:")
        if edges:
            for edge in edges:
                lines.append(f"- {edge.source_id} -[{edge.type}]-> {edge.target_id}")
        else:
            lines.append("- (none)")
        return "\n".join(lines)

    @staticmethod
    def _props(node: GraphNode) -> str:
        """Render a node's properties as a stable ``key=value`` suffix."""
        if not node.properties:
            return ""
        rendered = ", ".join(f"{key}={node.properties[key]}" for key in sorted(node.properties))
        return f": {rendered}"
