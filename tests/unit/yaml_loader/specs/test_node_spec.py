"""Tests for NodeSpec."""

from __future__ import annotations

import unittest

from pirn.yaml_loader.specs.node_spec import NodeSpec
from pydantic import ValidationError


class _ConcreteNode(NodeSpec):
    """Minimal concrete NodeSpec for testing the abstract base."""

    type: str = "test"


class TestNodeSpecConstruction(unittest.TestCase):
    def test_minimal_construction(self) -> None:
        n = _ConcreteNode(id="my_node", type="test")
        self.assertEqual(n.id, "my_node")
        self.assertIsNone(n.description)
        self.assertEqual(n.tags, [])
        self.assertEqual(n.error_policy, "skip_if_parent_failed")
        self.assertTrue(n.validate_io)

    def test_full_construction(self) -> None:
        n = _ConcreteNode(
            id="node_a",
            type="test",
            description="hello",
            tags=["a", "b"],
            error_policy="fail_fast",
            validate_io=False,
        )
        self.assertEqual(n.description, "hello")
        self.assertEqual(n.tags, ["a", "b"])
        self.assertEqual(n.error_policy, "fail_fast")
        self.assertFalse(n.validate_io)

    def test_empty_id_raises(self) -> None:
        with self.assertRaises(ValidationError):
            _ConcreteNode(id="", type="test")

    def test_extra_fields_forbidden(self) -> None:
        with self.assertRaises(ValidationError):
            _ConcreteNode(id="x", type="test", unknown_field="boom")
