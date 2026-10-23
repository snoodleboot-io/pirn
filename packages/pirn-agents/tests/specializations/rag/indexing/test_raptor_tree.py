"""Unit tests for :class:`RaptorTree` invariants."""

from __future__ import annotations

import unittest

from pirn.core.payload import Payload

from pirn_agents.specializations.base.nested_audit_value import NestedAuditValue
from pirn_agents.specializations.rag.indexing.raptor_node import RaptorNode
from pirn_agents.specializations.rag.indexing.raptor_tree import RaptorTree
from pirn_agents.specializations.rag.indexing.raptor_tree_frame import RaptorTreeFrame


class TestRaptorTree(unittest.TestCase):
    def _node(self) -> RaptorNode:
        return RaptorNode.create(id="raptor:abc:0:0", level=0, text="leaf", vector=[0.1, 0.2])

    def test_valid_tree_is_constructed(self) -> None:
        root = self._node()
        tree = RaptorTree(
            content_hash="abc123", node_count=3, level_count=2, reused=False, root=root
        )
        assert (
            tree.metadata.content_hash,
            tree.metadata.node_count,
            tree.metadata.level_count,
        ) == (
            "abc123",
            3,
            2,
        )
        assert tree.metadata.reused is False
        assert tree.data is root

    def test_empty_corpus_tree_is_valid(self) -> None:
        tree = RaptorTree(content_hash="abc", node_count=0, level_count=0, reused=False)
        assert tree.data is None

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

    def test_is_payload_of_frame_and_root(self) -> None:
        tree = RaptorTree(content_hash="abc", node_count=1, level_count=1, reused=True)
        assert isinstance(tree, Payload)
        assert isinstance(tree.metadata, RaptorTreeFrame)

    def test_audit_dict_has_both_halves(self) -> None:
        root = self._node()
        tree = RaptorTree(content_hash="abc", node_count=1, level_count=1, reused=False, root=root)
        audit = NestedAuditValue._audit_form(tree)
        assert audit["content_hash"] == "abc"
        assert audit["reused"] is False
        assert audit["root"] == NestedAuditValue._audit_form(root)

    def test_audit_dict_empty_root_is_none(self) -> None:
        tree = RaptorTree(content_hash="abc", node_count=0, level_count=0, reused=False)
        assert NestedAuditValue._audit_form(tree)["root"] is None

    def test_equality_is_structural(self) -> None:
        root = self._node()
        a = RaptorTree(content_hash="abc", node_count=1, level_count=1, reused=False, root=root)
        b = RaptorTree(content_hash="abc", node_count=1, level_count=1, reused=False, root=root)
        c = RaptorTree(content_hash="abc", node_count=2, level_count=1, reused=False, root=root)
        assert a == b
        assert a != c
