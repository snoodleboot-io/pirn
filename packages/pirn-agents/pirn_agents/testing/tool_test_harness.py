"""Tool testing kit — assertions and drivers for unit-testing a tool capability.

The kit gives tool authors two things:

* **Schema assertions** — :func:`assert_tool_schema` (exact match) and
  :func:`assert_schema_shape` (partial: required names + per-property
  fragments) check the declaration a tool advertises.
* **Invocation drivers** — :func:`invoke_tool` runs one call outside the
  engine and returns its value (raising on a failed call) and
  :func:`collect_tool_stream` drains a streaming tool, both returning the
  observed output for assertion.

Every helper accepts anything :meth:`ToolFactory.of` accepts — a ``Tool``
class, a ``@tool`` factory, a :class:`StubTool`, a bound factory (ADR
agents-speaks-core, WS1).  :class:`ToolTestHarness` bundles a single tool
with those helpers for a fluent style. Worked example::

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

from pirn.core.err import Err
from pirn.core.ok import Ok

from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory


class ToolTestHarness:
    """Bundles one tool capability with schema assertions and invocation drivers.

    The static methods below (prefixed ``_``) are the shared implementation
    for both the instance API and the module-level free functions
    (:func:`make_stub_tool`, :func:`assert_tool_schema`,
    :func:`assert_schema_shape`, :func:`invoke_tool`,
    :func:`collect_tool_stream`) documented as public API in
    ``pirn_agents/testing/__init__.py``.
    """

    def __init__(self, tool: Any) -> None:
        """Wrap ``tool`` for testing.

        Raises
        ------
        TypeError
            If ``tool`` is not a tool capability :meth:`ToolFactory.of` accepts.
        """
        self._tool = ToolFactory.of(tool)

    @property
    def tool(self) -> ToolFactory:
        """Return the wrapped capability."""
        return self._tool

    def assert_schema(self, expected: Mapping[str, Any]) -> None:
        """Assert the tool's declared parameters equal ``expected`` exactly."""
        ToolTestHarness._assert_tool_schema(self._tool, expected)

    def assert_schema_shape(
        self,
        *,
        required: Iterable[str] | None = None,
        properties: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """Assert the tool's declaration names ``required`` and ``properties``."""
        ToolTestHarness._assert_schema_shape(self._tool, required=required, properties=properties)

    async def run(self, arguments: Mapping[str, Any]) -> Any:
        """Run one call outside the engine and return its value."""
        return await ToolTestHarness._invoke_tool(self._tool, arguments)

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        """Run one call outside the engine and return its value (alias of :meth:`run`)."""
        return await ToolTestHarness._invoke_tool(self._tool, arguments)

    async def collect_stream(self, arguments: Mapping[str, Any]) -> list[Any]:
        """Drain the wrapped streaming tool into a list of chunks."""
        return await ToolTestHarness._collect_tool_stream(self._tool, arguments)

    async def assert_invokes_to(self, arguments: Mapping[str, Any], expected: Any) -> None:
        """Assert a call with ``arguments`` returns ``expected``."""
        result = await self.run(arguments)
        if result != expected:
            raise AssertionError(
                f"tool {self._tool.name!r} call mismatch:\n"
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

    @staticmethod
    def _make_stub_tool(**kwargs: Any) -> StubTool:
        """Return a :class:`StubTool` configured by ``kwargs`` (factory helper)."""
        return StubTool(**kwargs)

    @staticmethod
    def _assert_tool_schema(tool: Any, expected: Mapping[str, Any]) -> None:
        """Assert the tool's declared parameters equal ``expected`` exactly."""
        factory = ToolFactory.of(tool)
        actual = dict(factory.declaration().parameters)
        if actual != dict(expected):
            raise AssertionError(
                f"tool {factory.name!r} schema mismatch:\n"
                f"  expected={dict(expected)!r}\n  actual={actual!r}"
            )

    @staticmethod
    def _assert_schema_shape(
        tool: Any,
        *,
        required: Iterable[str] | None = None,
        properties: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """Assert ``tool``'s declaration names ``required`` and ``properties``.

        ``required`` (when given) must match the schema's required list as a
        set. Each entry in ``properties`` must appear in the schema's
        properties and contain at least the given key/values (a subset
        match), so callers can assert the interesting keys without pinning
        the whole fragment.
        """
        factory = ToolFactory.of(tool)
        schema = dict(factory.declaration().parameters)
        if required is not None:
            actual_required = set(schema.get("required", []))
            if actual_required != set(required):
                raise AssertionError(
                    f"tool {factory.name!r} required mismatch:\n"
                    f"  expected={set(required)!r}\n  actual={actual_required!r}"
                )
        if properties is not None:
            actual_props = dict(schema.get("properties", {}))
            for prop_name, expected_fragment in properties.items():
                if prop_name not in actual_props:
                    raise AssertionError(
                        f"tool {factory.name!r} missing property {prop_name!r}; "
                        f"have {sorted(actual_props)!r}"
                    )
                fragment = dict(actual_props[prop_name])
                for key, value in expected_fragment.items():
                    if fragment.get(key) != value:
                        raise AssertionError(
                            f"tool {factory.name!r} property {prop_name!r} key {key!r} mismatch:\n"
                            f"  expected={value!r}\n  actual={fragment.get(key)!r}"
                        )

    @staticmethod
    async def _invoke_tool(tool: Any, arguments: Mapping[str, Any]) -> Any:
        """Run one call of ``tool`` outside the engine and return its value.

        Raises
        ------
        ToolInvocationError
            If the call ends in ``Err`` (carrying the failure's type and
            message) or ``Skipped``.
        """
        factory = ToolFactory.of(tool)
        call = ToolCall(tool_name=factory.name, arguments=dict(arguments), call_id="harness")
        result = await factory.run_call(call)
        if isinstance(result, Ok):
            return result.value
        if isinstance(result, Err):
            raise ToolInvocationError(
                f"{result.record.exc_type}: {result.record.message}", call.call_id
            )
        raise ToolInvocationError(f"skipped: {result.reason}", call.call_id)

    @staticmethod
    async def _collect_tool_stream(tool: Any, arguments: Mapping[str, Any]) -> list[Any]:
        """Drain a streaming ``tool`` for ``arguments`` into a list of chunks.

        Raises
        ------
        TypeError
            If ``tool`` is not a streaming tool.
        """
        factory = ToolFactory.of(tool)
        if not factory.streaming:
            raise TypeError(f"tool {factory.name!r} is not a streaming tool")
        return await factory.collect_stream(arguments)


def make_stub_tool(**kwargs: Any) -> StubTool:
    """Return a :class:`StubTool` configured by ``kwargs`` (factory helper).

    Thin wrapper kept for the documented public import path (see
    ``pirn_agents/testing/__init__.py``); see :meth:`ToolTestHarness._make_stub_tool`.
    """
    return ToolTestHarness._make_stub_tool(**kwargs)  # pyright: ignore[reportPrivateUsage]  # public wrapper over the harness's own helper


def assert_tool_schema(tool: Any, expected: Mapping[str, Any]) -> None:
    """Assert ``tool``'s declared parameters equal ``expected`` exactly.

    Thin wrapper kept for the documented public import path; see
    :meth:`ToolTestHarness._assert_tool_schema`.
    """
    ToolTestHarness._assert_tool_schema(tool, expected)  # pyright: ignore[reportPrivateUsage]  # public wrapper over the harness's own helper


def assert_schema_shape(
    tool: Any,
    *,
    required: Iterable[str] | None = None,
    properties: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    """Assert ``tool``'s declaration names ``required`` and ``properties``.

    Thin wrapper kept for the documented public import path; see
    :meth:`ToolTestHarness._assert_schema_shape`.
    """
    ToolTestHarness._assert_schema_shape(tool, required=required, properties=properties)  # pyright: ignore[reportPrivateUsage]  # public wrapper over the harness's own helper


async def invoke_tool(tool: Any, arguments: Mapping[str, Any]) -> Any:
    """Run one call of ``tool`` outside the engine and return its value.

    Thin wrapper kept for the documented public import path; see
    :meth:`ToolTestHarness._invoke_tool`.
    """
    return await ToolTestHarness._invoke_tool(tool, arguments)  # pyright: ignore[reportPrivateUsage]  # public wrapper over the harness's own helper


async def collect_tool_stream(tool: Any, arguments: Mapping[str, Any]) -> list[Any]:
    """Drain a streaming ``tool`` for ``arguments`` into a list of chunks.

    Thin wrapper kept for the documented public import path; see
    :meth:`ToolTestHarness._collect_tool_stream`.

    Raises
    ------
    TypeError
        If ``tool`` is not a streaming tool.
    """
    return await ToolTestHarness._collect_tool_stream(tool, arguments)  # pyright: ignore[reportPrivateUsage]  # public wrapper over the harness's own helper
