"""Unit tests for :class:`PromptBinding` and its resolution order."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.prompt.prompt_catalog import PromptCatalog


def _catalog_with(name: str, body: str, *, namespace: str | None = None) -> PromptCatalog:
    catalog = PromptCatalog()
    pack: dict[str, object] = {"templates": {name: body}}
    if namespace is not None:
        pack["namespace"] = namespace
    catalog.load_mapping(pack)
    return catalog


class ConstructionTests(unittest.TestCase):
    """Field defaults and validation."""

    def test_defaults_to_the_builtin_namespace_and_no_pin(self) -> None:
        binding = PromptBinding(name="a.b", default="text")
        assert binding.namespace == PromptCatalog.builtin_namespace()
        assert binding.version is None

    def test_is_frozen(self) -> None:
        binding = PromptBinding(name="a.b", default="text")
        with self.assertRaises(FrozenInstanceError):
            binding.default = "other"  # type: ignore[misc]

    def test_rejects_empty_name(self) -> None:
        with self.assertRaisesRegex(TypeError, "name"):
            PromptBinding(name="", default="text")

    def test_rejects_non_string_default(self) -> None:
        with self.assertRaisesRegex(TypeError, "default"):
            PromptBinding(name="a", default=1)  # type: ignore[arg-type]

    def test_rejects_empty_namespace(self) -> None:
        with self.assertRaisesRegex(TypeError, "namespace"):
            PromptBinding(name="a", default="t", namespace="")

    def test_rejects_empty_version(self) -> None:
        with self.assertRaisesRegex(TypeError, "version"):
            PromptBinding(name="a", default="t", version="")


class ResolutionOrderTests(unittest.TestCase):
    """subclass override -> registered template -> built-in default."""

    def test_falls_back_to_the_builtin_default(self) -> None:
        binding = PromptBinding(name="a.b", default="builtin")
        assert binding.resolve(catalog=PromptCatalog()) == "builtin"

    def test_registered_template_beats_the_builtin_default(self) -> None:
        binding = PromptBinding(name="a.b", default="builtin")
        assert binding.resolve(catalog=_catalog_with("a.b", "loaded")) == "loaded"

    def test_declared_override_beats_a_registered_template(self) -> None:
        binding = PromptBinding(name="a.b", default="builtin")
        resolved = binding.resolve("subclass", catalog=_catalog_with("a.b", "loaded"))
        assert resolved == "subclass"

    def test_declared_value_equal_to_the_default_is_not_an_override(self) -> None:
        binding = PromptBinding(name="a.b", default="builtin")
        resolved = binding.resolve("builtin", catalog=_catalog_with("a.b", "loaded"))
        assert resolved == "loaded"

    def test_declared_override_wins_with_an_empty_catalog(self) -> None:
        binding = PromptBinding(name="a.b", default="builtin")
        assert binding.resolve("subclass", catalog=PromptCatalog()) == "subclass"

    def test_a_pack_in_another_namespace_is_ignored(self) -> None:
        binding = PromptBinding(name="a.b", default="builtin")
        catalog = _catalog_with("a.b", "loaded", namespace="somewhere-else")
        assert binding.resolve(catalog=catalog) == "builtin"

    def test_version_pin_selects_the_pinned_template(self) -> None:
        catalog = PromptCatalog()
        catalog.load_mapping({"templates": {"a.b": {"template": "v1", "version": "1.0.0"}}})
        catalog.load_mapping({"templates": {"a.b": {"template": "v2", "version": "2.0.0"}}})
        pinned = PromptBinding(name="a.b", default="builtin", version="1.0.0")
        floating = PromptBinding(name="a.b", default="builtin")
        assert pinned.resolve(catalog=catalog) == "v1"
        assert floating.resolve(catalog=catalog) == "v2"

    def test_variables_are_substituted_into_a_loaded_template(self) -> None:
        binding = PromptBinding(name="a.b", default="builtin")
        catalog = _catalog_with("a.b", "answer in {{ language }}")
        assert binding.resolve(variables={"language": "French"}, catalog=catalog) == (
            "answer in French"
        )

    def test_an_empty_loaded_body_is_honoured(self) -> None:
        # Deliberate: an operator who registers "" asked for no system prompt.
        binding = PromptBinding(name="a.b", default="builtin")
        assert binding.resolve(catalog=_catalog_with("a.b", "")) == ""


class SharedCatalogFallbackTests(unittest.TestCase):
    """With no explicit catalog the binding consults the process-wide one."""

    def setUp(self) -> None:
        PromptCatalog.reset_shared()

    def tearDown(self) -> None:
        PromptCatalog.reset_shared()

    def test_uses_the_shared_catalog_when_none_is_passed(self) -> None:
        PromptCatalog.shared().load_mapping({"templates": {"a.b": "from-shared"}})
        assert PromptBinding(name="a.b", default="builtin").resolve() == "from-shared"
