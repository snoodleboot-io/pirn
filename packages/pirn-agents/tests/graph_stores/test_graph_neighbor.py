"""Unit tests for :class:`GraphNeighbor` invariants."""

from __future__ import annotations

import unittest

from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_neighbor import GraphNeighbor
from pirn_agents.graph_stores.graph_node import GraphNode


class TestGraphNeighbor(unittest.TestCase):
    def _edge(self) -> GraphEdge:
        return GraphEdge.create(source_id="a", target_id="b", type="KNOWS")

    def _node(self) -> GraphNode:
        return GraphNode.create(id="b", type="Person")

    def test_valid_neighbor_is_constructed(self) -> None:
        edge = self._edge()
        node = self._node()
        neighbor = GraphNeighbor(edge=edge, node=node)
        assert neighbor.edge is edge
        assert neighbor.node is node

    def test_rejects_non_edge(self) -> None:
        with self.assertRaises(TypeError):
            GraphNeighbor(edge="not-an-edge", node=self._node())  # type: ignore[arg-type]

    def test_rejects_non_node(self) -> None:
        with self.assertRaises(TypeError):
            GraphNeighbor(edge=self._edge(), node="not-a-node")  # type: ignore[arg-type]
