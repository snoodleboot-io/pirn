"""Tests for PipelineLoader and load_pipeline."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pirn.yaml_loader.loader import PipelineLoader, load_pipeline
from pirn.yaml_loader.specs.pipeline_spec import PipelineSpec


class TestPipelineLoaderResolveType(unittest.TestCase):
    def test_builtins(self) -> None:
        for name, expected in [
            ("int", int),
            ("str", str),
            ("float", float),
            ("bool", bool),
            ("bytes", bytes),
            ("dict", dict),
            ("list", list),
        ]:
            with self.subTest(name=name):
                self.assertIs(PipelineLoader._resolve_type(name), expected)

    def test_generic_list_dict(self) -> None:
        result = PipelineLoader._resolve_type("list[dict]")
        self.assertEqual(result, list[dict])

    def test_dotted_path(self) -> None:
        result = PipelineLoader._resolve_type("pathlib.Path")
        import pathlib
        self.assertIs(result, pathlib.Path)

    def test_unknown_bare_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            PipelineLoader._resolve_type("UnknownType")


class TestPipelineLoaderResolveCallable(unittest.TestCase):
    def test_known_callables_lookup(self) -> None:
        fn = lambda x: x
        result = PipelineLoader._resolve_callable("my_fn", {"my_fn": fn}, False)
        self.assertIs(result, fn)

    def test_unknown_strict_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            PipelineLoader._resolve_callable("not.in.known", {}, False)

    def test_dotted_path_import(self) -> None:
        result = PipelineLoader._resolve_callable(
            "pathlib.Path", {}, True, allowed_module_prefixes=None
        )
        import pathlib
        self.assertIs(result, pathlib.Path)

    def test_allowlist_blocks_disallowed_module(self) -> None:
        with self.assertRaises(ValueError):
            PipelineLoader._resolve_callable(
                "pathlib.Path", {}, True, allowed_module_prefixes=["myapp"]
            )

    def test_allowlist_allows_matching_prefix(self) -> None:
        result = PipelineLoader._resolve_callable(
            "pathlib.Path", {}, True, allowed_module_prefixes=["pathlib"]
        )
        import pathlib
        self.assertIs(result, pathlib.Path)

    def test_non_dotted_ref_raises_in_loose_mode(self) -> None:
        with self.assertRaises(ValueError):
            PipelineLoader._resolve_callable("not_dotted", {}, True)

    def test_non_callable_in_known_raises(self) -> None:
        with self.assertRaises(TypeError):
            PipelineLoader._resolve_callable("x", {"x": 42}, False)


class TestPipelineLoaderTopoOrder(unittest.TestCase):
    def test_linear_chain(self) -> None:
        spec = PipelineSpec.model_validate({
            "nodes": [
                {"id": "k1", "type": "knot", "callable": "fn", "parents": {"data": "src"}},
                {"id": "src", "type": "source", "callable": "fn"},
            ]
        })
        ordered = PipelineLoader._topo_order_specs(spec)
        ids = [n.id for n in ordered]
        self.assertLess(ids.index("src"), ids.index("k1"))

    def test_unknown_parent_raises(self) -> None:
        spec = PipelineSpec.model_validate({
            "nodes": [
                {"id": "k1", "type": "knot", "callable": "fn", "parents": {"data": "missing"}},
            ]
        })
        with self.assertRaises(ValueError, msg="unknown parent"):
            PipelineLoader._topo_order_specs(spec)

    def test_empty_pipeline_returns_empty(self) -> None:
        spec = PipelineSpec()
        ordered = PipelineLoader._topo_order_specs(spec)
        self.assertEqual(ordered, [])


class TestAllowlistMerge(unittest.TestCase):
    """Test the caller/spec allowlist intersection logic."""

    def _make_spec(self, spec_prefixes):
        return PipelineSpec(
            allow_callable_refs=True,
            allowed_module_prefixes=spec_prefixes,
        )

    def test_both_none_gives_none(self) -> None:
        spec = self._make_spec(None)
        loader = PipelineLoader()
        # Simulate the merge logic directly.
        caller = None
        spec_list = spec.allowed_module_prefixes
        if caller is not None and spec_list is not None:
            effective = [p for p in caller if p in set(spec_list)]
        elif caller is not None:
            effective = caller
        else:
            effective = spec_list
        self.assertIsNone(effective)

    def test_caller_only_applies(self) -> None:
        spec = self._make_spec(None)
        caller = ["myapp"]
        spec_list = spec.allowed_module_prefixes
        if caller is not None and spec_list is not None:
            effective = [p for p in caller if p in set(spec_list)]
        elif caller is not None:
            effective = caller
        else:
            effective = spec_list
        self.assertEqual(effective, ["myapp"])

    def test_spec_only_applies(self) -> None:
        spec = self._make_spec(["myapp"])
        caller = None
        spec_list = spec.allowed_module_prefixes
        if caller is not None and spec_list is not None:
            effective = [p for p in caller if p in set(spec_list)]
        elif caller is not None:
            effective = caller
        else:
            effective = spec_list
        self.assertEqual(effective, ["myapp"])

    def test_intersection_used_when_both_set(self) -> None:
        spec = self._make_spec(["myapp", "shared"])
        caller = ["shared", "other"]
        spec_list = spec.allowed_module_prefixes
        if caller is not None and spec_list is not None:
            effective = [p for p in caller if p in set(spec_list)]
        elif caller is not None:
            effective = caller
        else:
            effective = spec_list
        self.assertEqual(effective, ["shared"])


class TestLoadPipelineWrapper(unittest.TestCase):
    def test_load_pipeline_is_callable(self) -> None:
        self.assertTrue(callable(load_pipeline))

    def test_non_mapping_yaml_raises(self) -> None:
        with self.assertRaises(ValueError):
            load_pipeline("- just_a_list")
