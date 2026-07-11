"""Tests for the :class:`SubGraphContextBuilder` knot (S4)."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.graph_rag.subgraph import Subgraph
from pirn_agents.graph_rag.subgraph_context_builder import SubGraphContextBuilder
from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.types.agent_message import AgentMessage


def _make_builder() -> SubGraphContextBuilder:
    with Tapestry():
        knot = SubGraphContextBuilder.__new__(SubGraphContextBuilder)
        object.__setattr__(knot, "_config", KnotConfig(id="ctx"))
    return knot


def _subgraph() -> Subgraph:
    return Subgraph(
        nodes=(
            GraphNode.create(id="b", type="Company", properties={"name": "Acme"}),
            GraphNode.create(id="a", type="Person", properties={"name": "Ada"}),
        ),
        edges=(GraphEdge.create(source_id="a", target_id="b", type="WORKS_AT"),),
    )


class TestSubGraphContextBuilder(unittest.IsolatedAsyncioTestCase):
    async def test_builds_agent_message(self) -> None:
        builder = _make_builder()
        messages = await builder.process(subgraph=_subgraph())
        assert len(messages) == 1
        message = messages[0]
        assert isinstance(message, AgentMessage)
        assert message.role == "system"
        assert message.name == "graph_context"

    async def test_content_is_stable_and_sorted(self) -> None:
        builder = _make_builder()
        content = (await builder.process(subgraph=_subgraph()))[0].content
        # Nodes are rendered sorted by id (a before b) for cache-stable output.
        assert content.index("a (Person)") < content.index("b (Company)")
        assert "name=Ada" in content
        assert "a -[WORKS_AT]-> b" in content

    async def test_custom_role_and_name(self) -> None:
        builder = _make_builder()
        messages = await builder.process(subgraph=_subgraph(), role="user", name="kg")
        assert messages[0].role == "user"
        assert messages[0].name == "kg"

    async def test_empty_subgraph_renders_none_markers(self) -> None:
        builder = _make_builder()
        content = (await builder.process(subgraph=Subgraph(nodes=(), edges=())))[0].content
        assert "Entities:\n- (none)" in content
        assert "Relations:\n- (none)" in content

    async def test_rejects_bad_subgraph(self) -> None:
        builder = _make_builder()
        with self.assertRaisesRegex(TypeError, "subgraph must be a Subgraph"):
            await builder.process(subgraph="nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
