"""Unit tests for :class:`pirn_agents.tool_registry.ToolRegistry` (S4)."""

from __future__ import annotations

import unittest

from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tool_registry import ToolRegistry
from pirn_agents.toolset import Toolset


def _registry() -> ToolRegistry:
    # Local registration keeps the shared sweet_tea registry untouched in tests.
    return ToolRegistry(mirror_to_sweet_tea=False)


class TestRegistration(unittest.TestCase):
    def test_register_and_get_exact_key(self) -> None:
        reg = _registry()
        tool = StubTool(name="search")
        reg.register(tool, namespace="web", version="1.0.0")
        assert reg.get("search", namespace="web", version="1.0.0") is tool
        assert len(reg) == 1

    def test_default_namespace_and_version(self) -> None:
        reg = _registry()
        tool = StubTool(name="calc")
        reg.register(tool)
        assert reg.get("calc") is tool
        assert reg.get("calc", namespace="default", version="1.0.0") is tool

    def test_non_tool_rejected(self) -> None:
        reg = _registry()
        with self.assertRaisesRegex(TypeError, "Tool"):
            reg.register("not-a-tool")  # type: ignore[arg-type]

    def test_duplicate_key_rejected(self) -> None:
        reg = _registry()
        reg.register(StubTool(name="dup"), namespace="a", version="1.0.0")
        with self.assertRaisesRegex(ValueError, "already registered"):
            reg.register(StubTool(name="dup"), namespace="a", version="1.0.0")

    def test_same_name_different_namespace_coexists(self) -> None:
        reg = _registry()
        a = StubTool(name="search")
        b = StubTool(name="search")
        reg.register(a, namespace="web")
        reg.register(b, namespace="db")
        assert reg.get("search", namespace="web") is a
        assert reg.get("search", namespace="db") is b


class TestVersionResolution(unittest.TestCase):
    def test_latest_version_resolved_without_version(self) -> None:
        reg = _registry()
        old = StubTool(name="search")
        new = StubTool(name="search")
        reg.register(old, namespace="web", version="1.9.0")
        reg.register(new, namespace="web", version="1.10.0")
        # Numeric-aware ordering: 1.10.0 > 1.9.0.
        assert reg.get("search", namespace="web") is new
        assert reg.latest_version("search", namespace="web") == "1.10.0"

    def test_versions_listed_low_to_high(self) -> None:
        reg = _registry()
        reg.register(StubTool(name="s"), namespace="n", version="2.0.0")
        reg.register(StubTool(name="s"), namespace="n", version="1.0.0")
        assert reg.versions("s", namespace="n") == ["1.0.0", "2.0.0"]

    def test_miss_returns_none(self) -> None:
        reg = _registry()
        assert reg.get("absent") is None
        assert reg.latest_version("absent") is None
        assert reg.versions("absent") == []


class TestIntrospection(unittest.TestCase):
    def test_namespaces_sorted_unique(self) -> None:
        reg = _registry()
        reg.register(StubTool(name="a"), namespace="z")
        reg.register(StubTool(name="b"), namespace="a")
        reg.register(StubTool(name="c"), namespace="a")
        assert reg.namespaces() == ["a", "z"]

    def test_contains_key_tuple(self) -> None:
        reg = _registry()
        reg.register(StubTool(name="s"), namespace="n", version="1.0.0")
        assert ("n", "s", "1.0.0") in reg
        assert ("n", "s", "9.9.9") not in reg


class TestComposition(unittest.TestCase):
    def test_compose_by_namespace_returns_toolset(self) -> None:
        reg = _registry()
        a = StubTool(name="a")
        b = StubTool(name="b")
        reg.register(a, namespace="web")
        reg.register(b, namespace="web")
        reg.register(StubTool(name="c"), namespace="db")
        composed = reg.compose(namespace="web")
        assert isinstance(composed, Toolset)
        assert [t.name for t in composed] == ["a", "b"]

    def test_compose_all_namespaces(self) -> None:
        reg = _registry()
        reg.register(StubTool(name="a"), namespace="web")
        reg.register(StubTool(name="b"), namespace="db")
        assert {t.name for t in reg.compose()} == {"a", "b"}

    def test_compose_by_tags(self) -> None:
        reg = _registry()
        reg.register(StubTool(name="search"), namespace="web", tags=["read", "net"])
        reg.register(StubTool(name="write"), namespace="web", tags=["mutate"])
        composed = reg.compose(tags=["read"])
        assert [t.name for t in composed] == ["search"]

    def test_compose_picks_latest_version_per_name(self) -> None:
        reg = _registry()
        old = StubTool(name="search")
        new = StubTool(name="search")
        reg.register(old, namespace="web", version="1.0.0", tags=["x"])
        reg.register(new, namespace="web", version="2.0.0", tags=["x"])
        composed = reg.compose(namespace="web")
        # Unique names only — the newest version wins, so Toolset stays valid.
        assert len(composed) == 1
        assert composed.get("search") is new


if __name__ == "__main__":
    unittest.main()
