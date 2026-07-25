"""Unit tests for :class:`PromptTemplateRegistry` — CRUD and versioning."""

from __future__ import annotations

import unittest

from pirn_agents.prompt.prompt_template import PromptTemplate
from pirn_agents.prompt.prompt_template_registry import PromptTemplateRegistry


def _tpl(name: str, version: str) -> PromptTemplate:
    return PromptTemplate(name=name, version=version, template=f"{name} {version}")


class TestRegister(unittest.TestCase):
    def test_register_and_get_exact_version(self) -> None:
        reg = PromptTemplateRegistry()
        reg.register(_tpl("greet", "1.0.0"))
        got = reg.get("greet", version="1.0.0")
        assert got is not None
        assert got.version == "1.0.0"
        assert len(reg) == 1

    def test_get_resolves_latest_version_numerically(self) -> None:
        reg = PromptTemplateRegistry()
        reg.register(_tpl("greet", "1.9.0"))
        reg.register(_tpl("greet", "1.10.0"))
        got = reg.get("greet")
        assert got is not None
        assert got.version == "1.10.0"
        assert reg.latest_version("greet") == "1.10.0"

    def test_versions_lists_lowest_first(self) -> None:
        reg = PromptTemplateRegistry()
        reg.register(_tpl("greet", "2.0.0"))
        reg.register(_tpl("greet", "1.0.0"))
        assert reg.versions("greet") == ["1.0.0", "2.0.0"]

    def test_namespaces_isolate_templates(self) -> None:
        reg = PromptTemplateRegistry()
        reg.register(_tpl("greet", "1.0.0"), namespace="a")
        reg.register(_tpl("greet", "1.0.0"), namespace="b")
        assert reg.namespaces() == ["a", "b"]
        assert reg.get("greet", namespace="a") is not None
        assert ("a", "greet", "1.0.0") in reg

    def test_duplicate_key_raises(self) -> None:
        reg = PromptTemplateRegistry()
        reg.register(_tpl("greet", "1.0.0"))
        with self.assertRaisesRegex(ValueError, "already registered"):
            reg.register(_tpl("greet", "1.0.0"))

    def test_register_rejects_non_template(self) -> None:
        reg = PromptTemplateRegistry()
        with self.assertRaisesRegex(TypeError, "PromptTemplate"):
            reg.register("nope")  # type: ignore[arg-type]


class TestLookupMisses(unittest.TestCase):
    def test_get_missing_returns_none(self) -> None:
        reg = PromptTemplateRegistry()
        assert reg.get("absent") is None
        assert reg.get("absent", version="1.0.0") is None
        assert reg.latest_version("absent") is None
        assert reg.versions("absent") == []


class TestUnregister(unittest.TestCase):
    def test_unregister_removes_entry(self) -> None:
        reg = PromptTemplateRegistry()
        reg.register(_tpl("greet", "1.0.0"))
        reg.register(_tpl("greet", "2.0.0"))
        assert reg.unregister("greet", version="1.0.0") is True
        assert reg.versions("greet") == ["2.0.0"]
        assert reg.get("greet", version="1.0.0") is None

    def test_unregister_last_version_clears_name(self) -> None:
        reg = PromptTemplateRegistry()
        reg.register(_tpl("greet", "1.0.0"))
        assert reg.unregister("greet", version="1.0.0") is True
        assert reg.latest_version("greet") is None
        assert reg.names() == []

    def test_unregister_missing_returns_false(self) -> None:
        reg = PromptTemplateRegistry()
        assert reg.unregister("greet", version="1.0.0") is False

    def test_names_lists_registered(self) -> None:
        reg = PromptTemplateRegistry()
        reg.register(_tpl("b", "1.0.0"))
        reg.register(_tpl("a", "1.0.0"))
        assert reg.names() == ["a", "b"]


if __name__ == "__main__":
    unittest.main()
