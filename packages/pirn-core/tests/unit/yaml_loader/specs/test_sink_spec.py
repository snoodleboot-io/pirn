"""Tests for SinkSpec."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from pirn.yaml_loader.specs.sink_spec import SinkSpec


class TestSinkSpecConstruction(unittest.TestCase):
    def test_minimal(self) -> None:
        s = SinkSpec(id="snk1", type="sink", callable="mymod.Sink")
        self.assertEqual(s.callable, "mymod.Sink")
        self.assertEqual(s.parents, {})
        self.assertEqual(s.config, {})

    def test_with_parents_and_config(self) -> None:
        s = SinkSpec(
            id="snk2",
            type="sink",
            callable="mymod.Sink",
            parents={"data": "transform1"},
            config={"output_path": "/tmp/out"},
        )
        self.assertEqual(s.parents["data"], "transform1")
        self.assertEqual(s.config["output_path"], "/tmp/out")

    def test_wrong_type_raises(self) -> None:
        with self.assertRaises(ValidationError):
            SinkSpec(id="x", type="source", callable="fn")

    def test_missing_callable_raises(self) -> None:
        with self.assertRaises(ValidationError):
            SinkSpec(id="x", type="sink")
