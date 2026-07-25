"""Tool testing kit — assertions and drivers for unit-testing a :class:`Tool`.

The kit gives tool authors two things:

* **Schema assertions** — :func:`assert_tool_schema` (exact match) and
  :func:`assert_schema_shape` (partial: required names + per-property
  fragments) check the schema a tool advertises.
* **Invocation drivers** — :func:`invoke_tool` drives sync/async tools and
  :func:`collect_tool_stream` drains a streaming tool, both returning the
  observed output for assertion.

:class:`ToolTestHarness` bundles a single tool with those helpers for a fluent
style. Worked example::

    from pirn_agents.testing import ToolTestHarness, make_stub_tool

    async def test_echo() -> None:
        harness = ToolTestHarness(make_stub_tool(name="echo", result="hi"))
        harness.assert_schema_shape(required=(), properties={"input": {"type": "string"}})
        assert await harness.invoke({"input": "x"}) == "hi"

    async def test_stream() -> None:
        harness = ToolTestHarness(make_stub_tool(name="gen", stream_chunks=["a", "b"]))
        assert await harness.collect_stream({}) == ["a", "b"]
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tool import Tool


def make_stub_tool(**kwargs: Any) -> StubTool:
    """Return a :class:`StubTool` configured by ``kwargs`` (factory helper)."""
    return StubTool(**kwargs)


def assert_tool_schema(tool: Tool, expected: Mapping[str, Any]) -> None:
    """Assert ``tool.parameters_schema`` equals ``expected`` exactly."""
    actual = dict(tool.parameters_schema)
    if actual != dict(expected):
        raise AssertionError(
            f"tool {tool.name!r} schema mismatch:\n  expected={dict(expected)!r}\n  actual={actual!r}"
        )


def assert_schema_shape(
    tool: Tool,
    *,
    required: Iterable[str] | None = None,
    properties: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    """Assert ``tool``'s schema declares ``required`` names and ``properties``.

    ``required`` (when given) must match the schema's required list as a set.
    Each entry in ``properties`` must appear in the schema's properties and
    contain at least the given key/values (a subset match), so callers can
    assert the interesting keys without pinning the whole fragment.
    """
    schema = dict(tool.parameters_schema)
    if required is not None:
        actual_required = set(schema.get("required", []))
        if actual_required != set(required):
            raise AssertionError(
                f"tool {tool.name!r} required mismatch:\n"
                f"  expected={set(required)!r}\n  actual={actual_required!r}"
            )
    if properties is not None:
        actual_props = dict(schema.get("properties", {}))
        for prop_name, expected_fragment in properties.items():
            if prop_name not in actual_props:
                raise AssertionError(
                    f"tool {tool.name!r} missing property {prop_name!r}; "
                    f"have {sorted(actual_props)!r}"
                )
            fragment = dict(actual_props[prop_name])
            for key, value in expected_fragment.items():
                if fragment.get(key) != value:
                    raise AssertionError(
                        f"tool {tool.name!r} property {prop_name!r} key {key!r} mismatch:\n"
                        f"  expected={value!r}\n  actual={fragment.get(key)!r}"
                    )


async def invoke_tool(tool: Tool, arguments: Mapping[str, Any]) -> Any:
    """Drive ``tool.invoke`` and return the result (sync/async tools alike)."""
    return await tool.invoke(arguments)


async def collect_tool_stream(tool: Tool, arguments: Mapping[str, Any]) -> list[Any]:
    """Drain a streaming ``tool`` for ``arguments`` into a list of chunks.

    Raises
    ------
    TypeError
        If ``tool`` is not a streaming tool.
    """
    if not tool.streaming:
        raise TypeError(f"tool {tool.name!r} is not a streaming tool")
    return await tool.collect_stream(arguments)


class ToolTestHarness:
    """Bundles one :class:`Tool` with schema assertions and invocation drivers."""

    def __init__(self, tool: Tool) -> None:
        """Wrap ``tool`` for testing.

        Raises
        ------
        TypeError
            If ``tool`` is not a :class:`Tool`.
        """
        if not isinstance(tool, Tool):
            raise TypeError(f"tool must be a Tool, got {type(tool).__name__}")
        self._tool = tool

    @property
    def tool(self) -> Tool:
        """Return the wrapped tool."""
        return self._tool

    def assert_schema(self, expected: Mapping[str, Any]) -> None:
        """Assert the tool's schema equals ``expected`` exactly."""
        assert_tool_schema(self._tool, expected)

    def assert_schema_shape(
        self,
        *,
        required: Iterable[str] | None = None,
        properties: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """Assert the tool's schema declares ``required`` names and ``properties``."""
        assert_schema_shape(self._tool, required=required, properties=properties)

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        """Drive the wrapped tool and return its result."""
        return await invoke_tool(self._tool, arguments)

    async def collect_stream(self, arguments: Mapping[str, Any]) -> list[Any]:
        """Drain the wrapped streaming tool into a list of chunks."""
        return await collect_tool_stream(self._tool, arguments)

    async def assert_invokes_to(self, arguments: Mapping[str, Any], expected: Any) -> None:
        """Assert invoking with ``arguments`` returns ``expected``."""
        result = await self.invoke(arguments)
        if result != expected:
            raise AssertionError(
                f"tool {self._tool.name!r} invoke mismatch:\n"
                f"  expected={expected!r}\n  actual={result!r}"
            )

    async def assert_streams(self, arguments: Mapping[str, Any], expected: list[Any]) -> None:
        """Assert streaming with ``arguments`` yields exactly ``expected``."""
        chunks = await self.collect_stream(arguments)
        if chunks != expected:
            raise AssertionError(
                f"tool {self._tool.name!r} stream mismatch:\n"
                f"  expected={expected!r}\n  actual={chunks!r}"
            )
