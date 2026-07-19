"""Unit tests for the rich, parametrised form of ``@tool`` (S1)."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from pirn_agents.function_tool import FunctionTool
from pirn_agents.tool import Tool
from pirn_agents.tool_decorator import tool
from pirn_agents.tool_permissions import ToolPermissions

# ----------------------------------------------------------------- fixtures


class SearchArgs(BaseModel):
    """Pydantic arg model with a per-field description."""

    query: str = Field(description="the search query")
    max_results: int = 5


@dataclass
class LookupArgs:
    topic: str
    limit: int = 3


@tool(args_model=SearchArgs)
async def model_search(args: SearchArgs) -> list[str]:
    """Search using a pydantic arg model."""
    return [args.query] * args.max_results


@tool(args_model=LookupArgs)
def dataclass_lookup(args: LookupArgs) -> str:
    """Look up using a dataclass arg model."""
    return f"{args.topic}:{args.limit}"


@tool(arg_docs={"expression": "a math expression"}, examples={"expression": "2 + 2"})
def documented_calc(expression: str) -> str:
    """Evaluate with documented arguments."""
    return str(eval(expression, {"__builtins__": {}}))


# ----------------------------------------------------------------- backward compat


class TestBackwardCompatibility(unittest.TestCase):
    def test_bare_decorator_still_returns_function_tool(self) -> None:
        @tool
        async def plain(x: str) -> str:
            """Plain tool."""
            return x

        assert isinstance(plain, FunctionTool)
        assert isinstance(plain, Tool)
        assert plain.name == "plain"

    def test_bare_decorator_schema_unchanged(self) -> None:
        @tool
        async def plain(query: str, max_results: int = 5) -> str:
            """Plain tool."""
            return query

        assert plain.parameters_schema == {
            "type": "object",
            "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}},
            "required": ["query"],
        }

    def test_default_permissions_are_inert(self) -> None:
        @tool
        async def plain() -> str:
            """Plain tool."""
            return ""

        assert plain.permissions.is_default is True

    def test_non_callable_still_raises(self) -> None:
        with self.assertRaisesRegex(TypeError, "callable"):
            tool("not a function")  # type: ignore[arg-type]


# ----------------------------------------------------------------- pydantic args


class TestPydanticArgs(unittest.TestCase):
    def test_schema_from_model(self) -> None:
        props = model_search.parameters_schema["properties"]
        assert props["query"]["type"] == "string"
        assert props["max_results"]["type"] == "integer"
        assert "query" in model_search.parameters_schema["required"]

    def test_per_arg_description_surfaces(self) -> None:
        assert model_search.parameters_schema["properties"]["query"]["description"] == (
            "the search query"
        )

    def test_validates_and_coerces_arguments(self) -> None:
        # "3" is coerced to int 3 by the pydantic model.
        result = asyncio.run(model_search.invoke({"query": "hi", "max_results": "3"}))
        assert result == ["hi", "hi", "hi"]

    def test_invalid_arguments_raise(self) -> None:
        with self.assertRaises(ValidationError):
            asyncio.run(model_search.invoke({"max_results": 2}))  # missing required query


class TestDataclassArgs(unittest.TestCase):
    def test_schema_from_dataclass(self) -> None:
        props = dataclass_lookup.parameters_schema["properties"]
        assert props["topic"]["type"] == "string"
        assert props["limit"]["type"] == "integer"
        assert dataclass_lookup.parameters_schema["required"] == ["topic"]

    def test_sync_dataclass_invocation(self) -> None:
        assert asyncio.run(dataclass_lookup.invoke({"topic": "refunds"})) == "refunds:3"


# ----------------------------------------------------------------- return schema


class TestReturnSchema(unittest.TestCase):
    def test_scalar_return_schema(self) -> None:
        @tool
        async def scalar() -> int:
            """Return an int."""
            return 1

        assert scalar.return_schema == {"type": "integer"}

    def test_list_return_schema(self) -> None:
        assert model_search.return_schema == {"type": "array", "items": {"type": "string"}}

    def test_no_annotation_is_none(self) -> None:
        @tool
        async def untyped():  # type: ignore[no-untyped-def]
            """No return annotation."""
            return 1

        assert untyped.return_schema is None

    def test_none_return_is_none(self) -> None:
        @tool
        async def returns_none() -> None:
            """Returns None."""
            return None

        assert returns_none.return_schema is None


# ----------------------------------------------------------------- arg docs / examples


class TestArgDocsAndExamples(unittest.TestCase):
    def test_arg_docs_surface_in_schema(self) -> None:
        prop = documented_calc.parameters_schema["properties"]["expression"]
        assert prop["description"] == "a math expression"

    def test_examples_surface_in_schema(self) -> None:
        prop = documented_calc.parameters_schema["properties"]["expression"]
        assert prop["examples"] == ["2 + 2"]


# ----------------------------------------------------------------- describe()


class TestDescribe(unittest.TestCase):
    def test_describe_core_shape_matches_toolset_entry(self) -> None:
        @tool
        async def plain(x: str) -> str:
            """Plain tool."""
            return x

        descriptor = plain.describe()
        assert set(descriptor) == {"name", "description", "parameters", "returns"}
        assert descriptor["name"] == "plain"

    def test_describe_includes_permissions_when_non_default(self) -> None:
        @tool(scope="db:write", mutating=True, cost_hint=1.5)
        async def writer(x: str) -> str:
            """Writer tool."""
            return x

        descriptor = writer.describe()
        assert descriptor["permissions"] == {
            "scope": "db:write",
            "mutating": True,
            "cost_hint": 1.5,
        }

    def test_describe_omits_permissions_when_default(self) -> None:
        @tool
        async def plain() -> str:
            """Plain tool."""
            return ""

        assert "permissions" not in plain.describe()


# ----------------------------------------------------------------- overrides / errors


class TestOverridesAndErrors(unittest.TestCase):
    def test_name_and_description_override(self) -> None:
        @tool(name="renamed", description="custom description")
        async def original() -> str:
            """Original docstring."""
            return ""

        assert original.name == "renamed"
        assert original.description == "custom description"

    def test_invalid_args_model_raises(self) -> None:
        with self.assertRaisesRegex(TypeError, "args_model"):

            @tool(args_model=int)
            async def bad(x: int) -> int:
                """Bad model."""
                return x

    def test_permissions_attached(self) -> None:
        @tool(scope="s", approval_required=True)
        async def gated() -> str:
            """Gated tool."""
            return ""

        assert isinstance(gated.permissions, ToolPermissions)
        assert gated.permissions.approval_required is True


if __name__ == "__main__":
    unittest.main()
