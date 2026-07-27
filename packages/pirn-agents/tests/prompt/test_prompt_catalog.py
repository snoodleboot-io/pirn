"""Unit tests for :class:`PromptCatalog`."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pirn_agents.prompt.prompt_catalog import PromptCatalog
from pirn_agents.prompt.prompt_template import PromptTemplate
from pirn_agents.prompt.prompt_template_registry import PromptTemplateRegistry


class ConstructionTests(unittest.TestCase):
    """Registry adoption and validation."""

    def test_creates_its_own_registry_by_default(self) -> None:
        catalog = PromptCatalog()
        assert isinstance(catalog.registry, PromptTemplateRegistry)
        assert len(catalog.registry) == 0

    def test_adopts_a_supplied_registry(self) -> None:
        registry = PromptTemplateRegistry()
        assert PromptCatalog(registry).registry is registry

    def test_rejects_a_non_registry(self) -> None:
        with self.assertRaisesRegex(TypeError, "PromptTemplateRegistry"):
            PromptCatalog("nope")  # type: ignore[arg-type]


class ResolveTests(unittest.TestCase):
    """Lookup and rendering behaviour."""

    def test_returns_none_when_nothing_is_registered(self) -> None:
        assert PromptCatalog().resolve("missing", namespace="pirn_agents") is None

    def test_renders_a_registered_template(self) -> None:
        catalog = PromptCatalog()
        catalog.registry.register(
            PromptTemplate(name="a", version="1.0.0", template="hello"), namespace="ns"
        )
        assert catalog.resolve("a", namespace="ns") == "hello"

    def test_resolves_the_newest_version_by_default(self) -> None:
        catalog = PromptCatalog()
        catalog.registry.register(PromptTemplate(name="a", version="1.0.0", template="old"))
        catalog.registry.register(PromptTemplate(name="a", version="1.10.0", template="new"))
        assert catalog.resolve("a", namespace="default") == "new"

    def test_pins_to_an_exact_version_when_asked(self) -> None:
        catalog = PromptCatalog()
        catalog.registry.register(PromptTemplate(name="a", version="1.0.0", template="old"))
        catalog.registry.register(PromptTemplate(name="a", version="1.10.0", template="new"))
        assert catalog.resolve("a", namespace="default", version="1.0.0") == "old"

    def test_substitutes_supplied_variables(self) -> None:
        catalog = PromptCatalog()
        catalog.registry.register(
            PromptTemplate(name="a", version="1.0.0", template="hi {{ who }}")
        )
        assert catalog.resolve("a", namespace="default", variables={"who": "you"}) == "hi you"

    def test_unfilled_slot_stays_literal_instead_of_raising(self) -> None:
        # Non-strict on purpose: a stray marker is visible to the operator, a
        # mid-turn PromptRenderError would take the agent down.
        catalog = PromptCatalog()
        catalog.registry.register(
            PromptTemplate(name="a", version="1.0.0", template="hi {{ who }}")
        )
        assert catalog.resolve("a", namespace="default") == "hi {{ who }}"


class LoadTests(unittest.TestCase):
    """Pack loading through the catalog."""

    def test_load_mapping_registers_and_reports_names(self) -> None:
        catalog = PromptCatalog()
        names = catalog.load_mapping({"templates": {"a": "x", "b": "y"}})
        assert names == ("a", "b")
        assert catalog.resolve("a", namespace=PromptCatalog.builtin_namespace()) == "x"

    def test_load_defaults_to_the_builtin_namespace(self) -> None:
        catalog = PromptCatalog()
        catalog.load_mapping({"templates": {"a": "x"}})
        assert catalog.registry.names(namespace=PromptCatalog.builtin_namespace()) == ["a"]

    def test_load_json_text(self) -> None:
        catalog = PromptCatalog()
        catalog.load_json(json.dumps({"templates": {"a": "x"}}))
        assert catalog.resolve("a", namespace=PromptCatalog.builtin_namespace()) == "x"

    def test_load_yaml_text(self) -> None:
        catalog = PromptCatalog()
        catalog.load_yaml("templates:\n  a: x\n")
        assert catalog.resolve("a", namespace=PromptCatalog.builtin_namespace()) == "x"

    def test_load_path_reads_a_file(self) -> None:
        catalog = PromptCatalog()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pack.yaml"
            path.write_text("templates:\n  a: from-file\n", encoding="utf-8")
            catalog.load_path(path)
        assert catalog.resolve("a", namespace=PromptCatalog.builtin_namespace()) == "from-file"

    def test_reloading_the_same_key_replaces_rather_than_raising(self) -> None:
        catalog = PromptCatalog()
        catalog.load_mapping({"templates": {"a": "first"}})
        catalog.load_mapping({"templates": {"a": "second"}})
        assert catalog.resolve("a", namespace=PromptCatalog.builtin_namespace()) == "second"
        assert len(catalog.registry) == 1


class SharedCatalogTests(unittest.TestCase):
    """The process-wide catalog and its environment-variable seeding."""

    def setUp(self) -> None:
        PromptCatalog.reset_shared()

    def tearDown(self) -> None:
        PromptCatalog.reset_shared()

    def test_shared_is_stable_across_calls(self) -> None:
        assert PromptCatalog.shared() is PromptCatalog.shared()

    def test_reset_shared_rebuilds_the_catalog(self) -> None:
        first = PromptCatalog.shared()
        PromptCatalog.reset_shared()
        assert PromptCatalog.shared() is not first

    def test_shared_is_empty_when_the_env_var_is_unset(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            assert len(PromptCatalog.shared().registry) == 0

    def test_env_var_packs_are_loaded_on_first_use(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pack.yaml"
            path.write_text("templates:\n  a: from-env\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {PromptCatalog.packs_env_var(): str(path)}):
                text = PromptCatalog.shared().resolve(
                    "a", namespace=PromptCatalog.builtin_namespace()
                )
        assert text == "from-env"

    def test_env_var_accepts_several_pathsep_separated_packs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "one.yaml"
            first.write_text("templates:\n  a: one\n", encoding="utf-8")
            second = Path(tmp) / "two.json"
            second.write_text(json.dumps({"templates": {"b": "two"}}), encoding="utf-8")
            joined = os.pathsep.join([str(first), "", str(second)])
            with mock.patch.dict(os.environ, {PromptCatalog.packs_env_var(): joined}):
                catalog = PromptCatalog.shared()
                namespace = PromptCatalog.builtin_namespace()
                assert catalog.resolve("a", namespace=namespace) == "one"
                assert catalog.resolve("b", namespace=namespace) == "two"

    def test_a_broken_pack_fails_loudly_rather_than_being_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pack.json"
            path.write_text("{not json", encoding="utf-8")
            with mock.patch.dict(os.environ, {PromptCatalog.packs_env_var(): str(path)}):
                with self.assertRaises(ValueError):
                    PromptCatalog.shared()

    def test_blank_env_var_loads_nothing(self) -> None:
        with mock.patch.dict(os.environ, {PromptCatalog.packs_env_var(): "   "}):
            assert PromptCatalog().load_environment_packs() == ()
