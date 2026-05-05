"""Tests for GateSpec."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from pirn.yaml_loader.specs.gate_spec import GateSpec


class TestGateSpecConstruction(unittest.TestCase):
    def test_minimal(self) -> None:
        s = GateSpec(id="gate1", type="gate", input="upstream", predicate="mymod.pred")
        self.assertEqual(s.id, "gate1")
        self.assertEqual(s.type, "gate")
        self.assertEqual(s.input, "upstream")
        self.assertEqual(s.predicate, "mymod.pred")

    def test_wrong_type_raises(self) -> None:
        with self.assertRaises(ValidationError):
            GateSpec(id="x", type="source", input="up", predicate="fn")

    def test_missing_input_raises(self) -> None:
        with self.assertRaises(ValidationError):
            GateSpec(id="x", type="gate", predicate="fn")

    def test_missing_predicate_raises(self) -> None:
        with self.assertRaises(ValidationError):
            GateSpec(id="x", type="gate", input="up")

    def test_inherits_description(self) -> None:
        s = GateSpec(
            id="g",
            type="gate",
            input="u",
            predicate="fn",
            description="filter odd rows",
        )
        self.assertEqual(s.description, "filter odd rows")
