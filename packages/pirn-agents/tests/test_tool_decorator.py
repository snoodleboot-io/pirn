"""Unit tests for the ``@tool`` decorator."""

from __future__ import annotations

import asyncio
import unittest

from pirn_agents.function_tool import FunctionTool
from pirn_agents.tool import Tool
from pirn_agents.tool_decorator import tool

# ----------------------------------------------------------------- fixtures


@tool
async def async_search(query: str, max_results: int = 5) -> str:
    """Search the web and return a summary of results."""
    return f"results:{query}"


@tool
def sync_calc(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return str(eval(expression, {"__builtins__": {}}))


@tool
async def optional_param(topic: str, context: str | None = None) -> str:
    """Look up a document, optionally scoped to a context."""
    return topic


@tool
async def list_param(items: list[str]) -> str:
    """Process a list of items."""
    return ",".join(items)


# ----------------------------------------------------------------- identity


class _StandaloneTests(unittest.TestCase):
    def test_produces_tool_instance(self):
        assert isinstance(async_search, Tool)
        assert isinstance(async_search, FunctionTool)

    def test_name_from_function(self):
        assert async_search.name == "async_search"
        assert sync_calc.name == "sync_calc"

    def test_description_from_docstring(self):
        assert async_search.description == "Search the web and return a summary of results."
        assert sync_calc.description == "Evaluate a mathematical expression."

    def test_description_first_paragraph_only(self):
        @tool
        async def multi_para() -> str:
            """First paragraph.

            Second paragraph that should be excluded.
            """
            return ""

        assert multi_para.description == "First paragraph."

    def test_description_fallback_to_name_when_no_docstring(self):
        @tool
        async def no_doc() -> str:
            return ""

        assert no_doc.description == "no_doc"

    # ----------------------------------------------------------------- schema

    def test_schema_required_and_optional(self):
        schema = async_search.parameters_schema
        assert schema["type"] == "object"
        assert "query" in schema["required"]
        assert "max_results" not in schema["required"]

    def test_schema_string_type(self):
        assert async_search.parameters_schema["properties"]["query"] == {"type": "string"}

    def test_schema_integer_type(self):
        assert async_search.parameters_schema["properties"]["max_results"] == {"type": "integer"}

    def test_schema_optional_nullable(self):
        prop = optional_param.parameters_schema["properties"]["context"]
        assert prop["type"] == ["string", "null"]
        assert "context" not in optional_param.parameters_schema.get("required", [])

    def test_schema_list_type(self):
        prop = list_param.parameters_schema["properties"]["items"]
        assert prop == {"type": "array", "items": {"type": "string"}}

    def test_schema_no_self_or_cls(self):
        class _Wrapper:
            @tool
            async def method(self, x: str) -> str:
                """A method wrapped as a tool."""
                return x

        # self should not appear in properties
        props = _Wrapper.method.parameters_schema["properties"]
        assert "self" not in props

    # ----------------------------------------------------------------- invocation

    def test_async_function_invoked(self):
        result = asyncio.run(async_search.invoke({"query": "pirn", "max_results": 3}))
        assert result == "results:pirn"

    def test_sync_function_invoked(self):
        result = asyncio.run(sync_calc.invoke({"expression": "3 * 7"}))
        assert result == "21"

    def test_optional_kwarg_omitted(self):
        result = asyncio.run(optional_param.invoke({"topic": "refund"}))
        assert result == "refund"

    # ----------------------------------------------------------------- error cases

    def test_non_callable_raises(self):
        with self.assertRaisesRegex(TypeError, "callable"):
            tool("not a function")  # type: ignore[arg-type]

    def test_top_level_import(self):
        from pirn_agents import FunctionTool as ImportedFunctionTool
        from pirn_agents import tool as imported_tool

        assert imported_tool is tool
        assert ImportedFunctionTool is FunctionTool
