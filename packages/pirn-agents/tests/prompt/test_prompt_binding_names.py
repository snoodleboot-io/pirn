"""Every shipped prompt's registered name is its owner's module path plus attribute (PIR-872).

``PROMPTS.md`` names a built-in ``PromptBinding`` by the owning module's dotted
path under ``pirn_agents`` plus the attribute name with any leading underscore
stripped. A class that moves to its own module takes its prompts' names with
it; no binding keeps the name of a module it no longer lives in.
"""

from __future__ import annotations

import importlib
import pkgutil
import unittest

import pirn_agents
from pirn_agents.prompt.prompt_binding import PromptBinding


class TestPromptBindingNamesMatchTheirOwner(unittest.TestCase):
    @staticmethod
    def owned_bindings() -> list[tuple[str, str, PromptBinding]]:
        """``(module, attribute, binding)`` for every binding declared in a class body."""
        found: list[tuple[str, str, PromptBinding]] = []
        for info in pkgutil.walk_packages(pirn_agents.__path__, f"{pirn_agents.__name__}."):
            module = importlib.import_module(info.name)
            for value in vars(module).values():
                if not isinstance(value, type) or value.__module__ != module.__name__:
                    continue
                for attribute, member in vars(value).items():
                    if isinstance(member, PromptBinding):
                        found.append((module.__name__, attribute, member))
        return found

    def test_the_inventory_is_not_empty(self) -> None:
        # Act.
        bindings = self.owned_bindings()

        # Assert: the walk reaches the shipped prompts, so the name check below cannot pass vacuously.
        self.assertGreater(len(bindings), 80)

    def test_every_binding_is_named_module_path_plus_attribute(self) -> None:
        # Arrange.
        prefix = f"{pirn_agents.__name__}."

        # Act.
        mismatched = [
            (binding.name, f"{module.removeprefix(prefix)}.{attribute.lstrip('_')}")
            for module, attribute, binding in self.owned_bindings()
            if binding.name != f"{module.removeprefix(prefix)}.{attribute.lstrip('_')}"
        ]

        # Assert.
        self.assertEqual(mismatched, [])

    def test_no_two_bindings_share_a_name(self) -> None:
        # Act.
        names = [binding.name for _, _, binding in self.owned_bindings()]

        # Assert.
        self.assertEqual(len(names), len(set(names)))
