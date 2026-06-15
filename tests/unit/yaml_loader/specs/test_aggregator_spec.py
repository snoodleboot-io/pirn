"""Tests for AggregatorSpec."""

from __future__ import annotations

import unittest

from pirn.yaml_loader.specs.aggregator_spec import AggregatorSpec
from pydantic import ValidationError


class TestAggregatorSpecConstruction(unittest.TestCase):
    def test_minimal(self) -> None:
        s = AggregatorSpec(id="agg1", type="aggregator", combine="mymod.combine")
        self.assertEqual(s.id, "agg1")
        self.assertEqual(s.type, "aggregator")
        self.assertEqual(s.combine, "mymod.combine")
        self.assertEqual(s.parents, {})

    def test_with_parents(self) -> None:
        s = AggregatorSpec(
            id="agg2",
            type="aggregator",
            combine="mymod.combine",
            parents={"a": "node_a", "b": "node_b"},
        )
        self.assertEqual(s.parents, {"a": "node_a", "b": "node_b"})

    def test_wrong_type_literal_raises(self) -> None:
        with self.assertRaises(ValidationError):
            AggregatorSpec(id="x", type="knot", combine="fn")

    def test_missing_combine_raises(self) -> None:
        with self.assertRaises(ValidationError):
            AggregatorSpec(id="x", type="aggregator")

    def test_inherits_node_spec_fields(self) -> None:
        s = AggregatorSpec(
            id="agg3",
            type="aggregator",
            combine="fn",
            tags=["etl"],
            error_policy="fail_fast",
        )
        self.assertEqual(s.tags, ["etl"])
        self.assertEqual(s.error_policy, "fail_fast")
