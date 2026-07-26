"""Unit tests for :class:`RaptorTree` invariants."""

from __future__ import annotations

import unittest

from pirn_agents.specializations.rag.indexing.raptor_node import RaptorNode
from pirn_agents.specializations.rag.indexing.raptor_tree import RaptorTree


class TestRaptorTree(unittest.TestCase):
    def _node(self) -> RaptorNode:
        return RaptorNode.create(id="raptor:abc:0:0", level=0, text="leaf", vector=[0.1, 0.2])

    def test_valid_tree_is_constructed(self) -> None:
        root = self._node()
        tree = RaptorTree(
            content_hash="abc123", node_count=3, level_count=2, reused=False, root=root
        )
        assert (tree.content_hash, tree.node_count, tree.level_count) == ("abc123", 3, 2)
        assert tree.root is root

    def test_empty_corpus_tree_is_valid(self) -> None:
        tree = RaptorTree(content_hash="abc", node_count=0, level_count=0, reused=False)
        assert tree.root is None

    def test_rejects_empty_content_hash(self) -> None:
        with self.assertRaises(TypeError):
            RaptorTree(content_hash="", node_count=1, level_count=1, reused=False)

    def test_rejects_negative_node_count(self) -> None:
        with self.assertRaises(ValueError):
            RaptorTree(content_hash="abc", node_count=-1, level_count=1, reused=False)

    def test_rejects_negative_level_count(self) -> None:
        with self.assertRaises(ValueError):
            RaptorTree(content_hash="abc", node_count=1, level_count=-1, reused=False)

    def test_rejects_bool_node_count(self) -> None:
        with self.assertRaises(TypeError):
            RaptorTree(content_hash="abc", node_count=True, level_count=1, reused=False)  # type: ignore[arg-type]

    def test_rejects_non_bool_reused(self) -> None:
        with self.assertRaises(TypeError):
            RaptorTree(content_hash="abc", node_count=1, level_count=1, reused=1)  # type: ignore[arg-type]

    def test_rejects_non_node_root(self) -> None:
        with self.assertRaises(TypeError):
            RaptorTree(
                content_hash="abc",
                node_count=1,
                level_count=1,
                reused=False,
                root="not-a-node",  # type: ignore[arg-type]
            )
