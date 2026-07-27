"""Unit tests for :class:`PromptPackLoader`."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pirn_agents.prompt.prompt_pack_loader import PromptPackLoader


class FromMappingTests(unittest.TestCase):
    """Parsing an already-decoded pack mapping."""

    def test_string_shorthand_uses_default_version(self) -> None:
        namespace, templates = PromptPackLoader.from_mapping(
            {"templates": {"a.b": "hello"}}, default_namespace="pirn_agents"
        )
        assert namespace == "pirn_agents"
        assert len(templates) == 1
        assert templates[0].name == "a.b"
        assert templates[0].template == "hello"
        assert templates[0].version == PromptPackLoader.default_version()

    def test_full_form_carries_version_description_and_partials(self) -> None:
        _, templates = PromptPackLoader.from_mapping(
            {
                "templates": {
                    "a.b": {
                        "template": "{{> lead }} then {{ tail }}",
                        "version": "2.1.0",
                        "description": "a description",
                        "partials": {"lead": "LEAD"},
                    }
                }
            },
            default_namespace="pirn_agents",
        )
        assert templates[0].version == "2.1.0"
        assert templates[0].description == "a description"
        assert templates[0].render({"tail": "TAIL"}) == "LEAD then TAIL"

    def test_explicit_namespace_overrides_the_default(self) -> None:
        namespace, _ = PromptPackLoader.from_mapping(
            {"namespace": "tenant-a", "templates": {"a": "x"}},
            default_namespace="pirn_agents",
        )
        assert namespace == "tenant-a"

    def test_file_order_is_preserved(self) -> None:
        _, templates = PromptPackLoader.from_mapping(
            {"templates": {"z": "1", "a": "2", "m": "3"}}, default_namespace="ns"
        )
        assert [t.name for t in templates] == ["z", "a", "m"]

    def test_rejects_non_mapping_pack(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a mapping"):
            PromptPackLoader.from_mapping(["nope"], default_namespace="ns")  # type: ignore[arg-type]

    def test_rejects_missing_templates_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "'templates'"):
            PromptPackLoader.from_mapping({"namespace": "ns"}, default_namespace="ns")

    def test_rejects_non_mapping_templates(self) -> None:
        with self.assertRaisesRegex(TypeError, "'templates' must be a mapping"):
            PromptPackLoader.from_mapping({"templates": ["a"]}, default_namespace="ns")

    def test_rejects_empty_namespace(self) -> None:
        with self.assertRaisesRegex(ValueError, "namespace"):
            PromptPackLoader.from_mapping(
                {"namespace": "", "templates": {"a": "x"}}, default_namespace="ns"
            )

    def test_rejects_entry_without_template_body(self) -> None:
        with self.assertRaisesRegex(ValueError, "must declare a string 'template'"):
            PromptPackLoader.from_mapping(
                {"templates": {"a": {"version": "1.0.0"}}}, default_namespace="ns"
            )

    def test_rejects_entry_of_wrong_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "string body or a mapping"):
            PromptPackLoader.from_mapping({"templates": {"a": 42}}, default_namespace="ns")

    def test_rejects_non_string_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "'version'"):
            PromptPackLoader.from_mapping(
                {"templates": {"a": {"template": "x", "version": 2}}}, default_namespace="ns"
            )

    def test_rejects_non_string_description(self) -> None:
        with self.assertRaisesRegex(ValueError, "'description'"):
            PromptPackLoader.from_mapping(
                {"templates": {"a": {"template": "x", "description": 2}}}, default_namespace="ns"
            )

    def test_rejects_non_mapping_partials(self) -> None:
        with self.assertRaisesRegex(TypeError, "'partials'"):
            PromptPackLoader.from_mapping(
                {"templates": {"a": {"template": "x", "partials": ["y"]}}},
                default_namespace="ns",
            )

    def test_rejects_empty_template_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty strings"):
            PromptPackLoader.from_mapping({"templates": {"": "x"}}, default_namespace="ns")


class FromTextTests(unittest.TestCase):
    """JSON and YAML text entry points."""

    def test_from_json_parses_a_pack(self) -> None:
        text = json.dumps({"namespace": "ns", "templates": {"a": "body"}})
        namespace, templates = PromptPackLoader.from_json(text, default_namespace="pirn_agents")
        assert namespace == "ns"
        assert templates[0].template == "body"

    def test_from_json_rejects_invalid_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            PromptPackLoader.from_json("{", default_namespace="ns")

    def test_from_json_rejects_non_object(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be an object"):
            PromptPackLoader.from_json("[1, 2]", default_namespace="ns")

    def test_from_yaml_parses_a_pack(self) -> None:
        namespace, templates = PromptPackLoader.from_yaml(
            "namespace: ns\ntemplates:\n  a.b: body\n", default_namespace="pirn_agents"
        )
        assert namespace == "ns"
        assert templates[0].name == "a.b"
        assert templates[0].template == "body"

    def test_from_yaml_rejects_non_mapping(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a mapping"):
            PromptPackLoader.from_yaml("- 1\n- 2\n", default_namespace="ns")


class FromPathTests(unittest.TestCase):
    """Suffix dispatch and the optional containment root."""

    def test_dispatches_json_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pack.json"
            path.write_text(json.dumps({"templates": {"a": "j"}}), encoding="utf-8")
            _, templates = PromptPackLoader.from_path(path, default_namespace="ns")
        assert templates[0].template == "j"

    def test_dispatches_yaml_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pack.yaml"
            path.write_text("templates:\n  a: y\n", encoding="utf-8")
            _, templates = PromptPackLoader.from_path(path, default_namespace="ns")
        assert templates[0].template == "y"

    def test_dispatches_yml_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pack.yml"
            path.write_text("templates:\n  a: y\n", encoding="utf-8")
            _, templates = PromptPackLoader.from_path(path, default_namespace="ns")
        assert templates[0].template == "y"

    def test_rejects_unsupported_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pack.txt"
            path.write_text("templates: {}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported suffix"):
                PromptPackLoader.from_path(path, default_namespace="ns")

    def test_allowed_root_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                PromptPackLoader.from_path(
                    "../outside.yaml", default_namespace="ns", allowed_root=tmp
                )

    def test_allowed_root_accepts_in_root_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pack.json").write_text(
                json.dumps({"templates": {"a": "ok"}}), encoding="utf-8"
            )
            _, templates = PromptPackLoader.from_path(
                "pack.json", default_namespace="ns", allowed_root=tmp
            )
        assert templates[0].template == "ok"
