"""Tests for :class:`pirn_agents.toolset.Toolset`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn_agents.tool import Tool
from pirn_agents.toolset import Toolset


class StubTool(Tool):
    """Minimal deterministic tool double."""

    def __init__(self, name: str, description: str = "stub tool") -> None:
        self._name = name
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {"input": {"type": "string"}}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        return "stub-result"


class TestToolsetConstruction(unittest.TestCase):
    def test_valid_tools_preserve_order(self) -> None:
        a, b, c = StubTool("a"), StubTool("b"), StubTool("c")
        ts = Toolset([a, b, c])
        assert len(ts) == 3
        assert list(ts) == [a, b, c]

    def test_empty_default(self) -> None:
        ts = Toolset()
        assert len(ts) == 0
        assert list(ts) == []

    def test_duplicate_name_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            Toolset([StubTool("dup"), StubTool("dup")])
        assert "dup" in str(ctx.exception)

    def test_non_tool_element_raises_type_error(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            Toolset([StubTool("a"), "not-a-tool"])  # type: ignore[list-item]
        message = str(ctx.exception)
        assert "1" in message
        assert "str" in message


class TestToolsetLookup(unittest.TestCase):
    def test_get_hit(self) -> None:
        a = StubTool("a")
        ts = Toolset([a, StubTool("b")])
        assert ts.get("a") is a

    def test_get_miss_returns_none(self) -> None:
        ts = Toolset([StubTool("a")])
        assert ts.get("missing") is None

    def test_contains(self) -> None:
        ts = Toolset([StubTool("a")])
        assert "a" in ts
        assert "b" not in ts

    def test_iteration_order(self) -> None:
        names = ["first", "second", "third"]
        ts = Toolset([StubTool(n) for n in names])
        assert [tool.name for tool in ts] == names


class TestToolsetSchema(unittest.TestCase):
    def test_schema_is_provider_neutral_one_per_tool(self) -> None:
        ts = Toolset([StubTool("a", "desc-a"), StubTool("b", "desc-b")])
        schema = ts.schema()
        assert len(schema) == 2
        assert schema[0] == {
            "name": "a",
            "description": "desc-a",
            "parameters": {"type": "object", "properties": {"input": {"type": "string"}}},
        }
        for entry in schema:
            assert set(entry.keys()) == {"name", "description", "parameters"}
            assert "function" not in entry
            assert "type" not in entry

    def test_schema_parameters_is_plain_dict(self) -> None:
        ts = Toolset([StubTool("a")])
        params = ts.schema()[0]["parameters"]
        assert isinstance(params, dict)


class TestToolsetMerge(unittest.TestCase):
    def test_add_preserves_order(self) -> None:
        a, b, c, d = StubTool("a"), StubTool("b"), StubTool("c"), StubTool("d")
        merged = Toolset([a, b]) + Toolset([c, d])
        assert list(merged) == [a, b, c, d]

    def test_merge_preserves_order(self) -> None:
        a, b, c = StubTool("a"), StubTool("b"), StubTool("c")
        merged = Toolset([a]).merge(Toolset([b, c]))
        assert list(merged) == [a, b, c]

    def test_cross_set_duplicate_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            Toolset([StubTool("shared")]) + Toolset([StubTool("shared")])
        assert "shared" in str(ctx.exception)


class TestToolsetAudit(unittest.TestCase):
    def test_audit_dict_returns_ordered_names(self) -> None:
        ts = Toolset([StubTool("x"), StubTool("y"), StubTool("z")])
        assert ts._pirn_audit_dict() == ["x", "y", "z"]


if __name__ == "__main__":
    unittest.main()
