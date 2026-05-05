"""Tests for PipelineSpec."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from pirn.yaml_loader.specs.pipeline_spec import PipelineSpec


class TestPipelineSpecConstruction(unittest.TestCase):
    def test_empty_pipeline(self) -> None:
        spec = PipelineSpec()
        self.assertIsNone(spec.name)
        self.assertIsNone(spec.description)
        self.assertFalse(spec.allow_callable_refs)
        self.assertIsNone(spec.allowed_module_prefixes)
        self.assertEqual(spec.nodes, [])

    def test_with_name_and_description(self) -> None:
        spec = PipelineSpec(name="my_pipeline", description="does stuff")
        self.assertEqual(spec.name, "my_pipeline")
        self.assertEqual(spec.description, "does stuff")

    def test_allow_callable_refs_flag(self) -> None:
        spec = PipelineSpec(allow_callable_refs=True, allowed_module_prefixes=["myapp"])
        self.assertTrue(spec.allow_callable_refs)
        self.assertEqual(spec.allowed_module_prefixes, ["myapp"])

    def test_extra_fields_forbidden(self) -> None:
        with self.assertRaises(ValidationError):
            PipelineSpec(unknown="boom")

    def test_nodes_by_id_empty(self) -> None:
        spec = PipelineSpec()
        self.assertEqual(spec.nodes_by_id, {})

    def test_nodes_by_id_populated(self) -> None:
        spec = PipelineSpec.model_validate({
            "nodes": [
                {"id": "src", "type": "source", "callable": "mymod.src"},
                {"id": "snk", "type": "sink", "callable": "mymod.snk"},
            ]
        })
        by_id = spec.nodes_by_id
        self.assertIn("src", by_id)
        self.assertIn("snk", by_id)
        self.assertEqual(by_id["src"].id, "src")

    def test_source_node_parsed(self) -> None:
        spec = PipelineSpec.model_validate({
            "nodes": [{"id": "s1", "type": "source", "callable": "mod.fn"}]
        })
        self.assertEqual(len(spec.nodes), 1)
        self.assertEqual(spec.nodes[0].type, "source")

    def test_mixed_node_types(self) -> None:
        spec = PipelineSpec.model_validate({
            "nodes": [
                {"id": "p1", "type": "parameter", "type_": "int"},
                {"id": "src", "type": "source", "callable": "mod.fn"},
                {"id": "k1", "type": "knot", "callable": "mod.kn", "parents": {"data": "src"}},
            ]
        })
        self.assertEqual(len(spec.nodes), 3)
