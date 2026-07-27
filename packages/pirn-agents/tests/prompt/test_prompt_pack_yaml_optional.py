"""PyYAML stays an optional extra for the prompt-pack loader.

The prompt layer must not drag PyYAML into the base install: importing
``pirn_agents`` — and loading a JSON pack, or resolving any built-in prompt —
has to work in an environment where PyYAML is absent, with the friendly
``pip install "pirn-agents[yaml]"`` message appearing only when a YAML pack is
actually read.

The dev venv *has* PyYAML, so absence is simulated by blocking the import in a
subprocess-free way: a meta-path finder that refuses to locate ``yaml``.
"""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Any

from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.prompt.prompt_catalog import PromptCatalog
from pirn_agents.prompt.prompt_pack_loader import PromptPackLoader


class _BlockYamlFinder(MetaPathFinder):
    """Meta-path finder that makes ``import yaml`` fail."""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        if fullname == "yaml" or fullname.startswith("yaml."):
            raise ImportError("No module named 'yaml'")
        return None


@contextmanager
def _yaml_absent() -> Iterator[None]:
    """Run the block with ``yaml`` unimportable and uncached."""
    finder = _BlockYamlFinder()
    cached = {name: mod for name, mod in sys.modules.items() if name.split(".")[0] == "yaml"}
    for name in cached:
        del sys.modules[name]
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        sys.meta_path.remove(finder)
        sys.modules.update(cached)


class YamlAbsenceTests(unittest.TestCase):
    """Behaviour of the prompt layer without the ``yaml`` extra installed."""

    def test_the_blocker_actually_blocks(self) -> None:
        with _yaml_absent():
            with self.assertRaises(ImportError):
                importlib.import_module("yaml")

    def test_importing_the_prompt_layer_works_without_pyyaml(self) -> None:
        with _yaml_absent():
            for module in (
                "pirn_agents.prompt.prompt_pack_loader",
                "pirn_agents.prompt.prompt_catalog",
                "pirn_agents.prompt.prompt_binding",
            ):
                sys.modules.pop(module, None)
            reloaded: Any = importlib.import_module("pirn_agents.prompt.prompt_binding")
            assert reloaded is not None
        # Restore the canonical module objects for the rest of the session.
        for module in (
            "pirn_agents.prompt.prompt_pack_loader",
            "pirn_agents.prompt.prompt_catalog",
            "pirn_agents.prompt.prompt_binding",
        ):
            importlib.import_module(module)

    def test_json_packs_still_load_without_pyyaml(self) -> None:
        with _yaml_absent():
            catalog = PromptCatalog()
            catalog.load_json(json.dumps({"templates": {"a.b": "json-body"}}))
            assert PromptBinding(name="a.b", default="builtin").resolve(catalog=catalog) == (
                "json-body"
            )

    def test_builtin_defaults_still_resolve_without_pyyaml(self) -> None:
        with _yaml_absent():
            binding = PromptBinding(name="nothing.registered", default="builtin")
            assert binding.resolve(catalog=PromptCatalog()) == "builtin"

    def test_yaml_pack_raises_the_friendly_install_hint(self) -> None:
        with _yaml_absent():
            with self.assertRaises(ImportError) as ctx:
                PromptPackLoader.from_yaml("templates:\n  a: x\n", default_namespace="ns")
        assert 'pip install "pirn-agents[yaml]"' in str(ctx.exception)

    def test_catalog_load_yaml_raises_the_friendly_install_hint(self) -> None:
        with _yaml_absent():
            with self.assertRaises(ImportError) as ctx:
                PromptCatalog().load_yaml("templates:\n  a: x\n")
        assert 'pip install "pirn-agents[yaml]"' in str(ctx.exception)


class ImportSurfaceTests(unittest.TestCase):
    """The prompt modules declare no module-level YAML import."""

    def test_no_prompt_module_imports_yaml_at_module_level(self) -> None:
        for name in (
            "pirn_agents.prompt.prompt_pack_loader",
            "pirn_agents.prompt.prompt_catalog",
            "pirn_agents.prompt.prompt_binding",
        ):
            module = importlib.import_module(name)
            assert not hasattr(module, "yaml"), f"{name} binds 'yaml' at module level"
