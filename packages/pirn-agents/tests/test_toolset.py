"""Tests for :class:`pirn_agents.tools.toolset.Toolset` — a registry of capabilities (ADR WS1)."""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.toolset import Toolset


class Alpha(Tool):
    """alpha tool"""

    tool_name: ClassVar[str] = "alpha"

    def __init__(self, *, input: Knot | str, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(input=input, _config=_config, **kwargs)

    async def process(self, input: str, **_: Any) -> str:
        return input


def _stub(name: str, description: str = "stub tool") -> StubTool:
    return StubTool(name=name, description=description)


class TestToolsetConstruction(unittest.TestCase):
    def test_valid_tools_preserve_order(self) -> None:
        a, b, c = _stub("a"), _stub("b"), _stub("c")
        ts = Toolset([a, b, c])
        assert len(ts) == 3
        assert list(ts) == [a, b, c]

    def test_a_tool_class_is_normalised_into_a_factory(self) -> None:
        ts = Toolset([Alpha])
        (factory,) = list(ts)
        assert isinstance(factory, ToolFactory)
        assert factory.knot_class is Alpha
        assert factory.name == "alpha"

    def test_a_bound_factory_is_kept_as_is(self) -> None:
        bound = Alpha.bind(input="fixed")
        ts = Toolset([bound])
        assert ts.get("alpha") is bound

    def test_empty_default(self) -> None:
        ts = Toolset()
        assert len(ts) == 0
        assert list(ts) == []

    def test_duplicate_name_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            Toolset([_stub("dup"), _stub("dup")])
        assert "dup" in str(ctx.exception)

    def test_non_tool_element_raises_type_error(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            Toolset([_stub("a"), "not-a-tool"])  # type: ignore[list-item]
        message = str(ctx.exception)
        assert "1" in message
        assert "str" in message


class TestToolsetLookup(unittest.TestCase):
    def test_get_hit(self) -> None:
        a = _stub("a")
        ts = Toolset([a, _stub("b")])
        assert ts.get("a") is a

    def test_get_miss_returns_none(self) -> None:
        ts = Toolset([_stub("a")])
        assert ts.get("missing") is None

    def test_contains(self) -> None:
        ts = Toolset([_stub("a")])
        assert "a" in ts
        assert "b" not in ts

    def test_iteration_order(self) -> None:
        names = ["first", "second", "third"]
        ts = Toolset([_stub(n) for n in names])
        assert [tool.name for tool in ts] == names


class TestToolsetSchema(unittest.TestCase):
    def test_schema_is_provider_neutral_one_per_tool(self) -> None:
        ts = Toolset([_stub("a", "desc-a"), _stub("b", "desc-b")])
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

    def test_schema_of_a_knot_class_derives_from_its_hints(self) -> None:
        assert Toolset([Alpha]).schema() == [
            {
                "name": "alpha",
                "description": "alpha tool",
                "parameters": {
                    "type": "object",
                    "properties": {"input": {"type": "string"}},
                    "required": ["input"],
                },
            }
        ]

    def test_schema_parameters_is_plain_dict(self) -> None:
        ts = Toolset([_stub("a")])
        params = ts.schema()[0]["parameters"]
        assert isinstance(params, dict)


class TestToolsetMerge(unittest.TestCase):
    def test_add_preserves_order(self) -> None:
        a, b, c, d = _stub("a"), _stub("b"), _stub("c"), _stub("d")
        merged = Toolset([a, b]) + Toolset([c, d])
        assert list(merged) == [a, b, c, d]

    def test_merge_preserves_order(self) -> None:
        a, b, c = _stub("a"), _stub("b"), _stub("c")
        merged = Toolset([a]).merge(Toolset([b, c]))
        assert list(merged) == [a, b, c]

    def test_cross_set_duplicate_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            Toolset([_stub("shared")]) + Toolset([_stub("shared")])
        assert "shared" in str(ctx.exception)


class TestToolsetAudit(unittest.TestCase):
    def test_audit_dict_returns_ordered_names(self) -> None:
        ts = Toolset([_stub("x"), _stub("y"), _stub("z")])
        assert ts._pirn_audit_dict() == ["x", "y", "z"]


if __name__ == "__main__":
    unittest.main()
