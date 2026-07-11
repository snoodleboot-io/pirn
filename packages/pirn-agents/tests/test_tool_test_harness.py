"""Tests for the tool testing kit helpers themselves (S5).

These exercise the kit against :class:`StubTool` fixtures to confirm its
assertions pass on matching tools and fail (raise ``AssertionError``) on
mismatches, and that its drivers handle sync, async, and streaming tools.
"""

from __future__ import annotations

import unittest

from pirn_agents.testing import (
    ToolTestHarness,
    assert_schema_shape,
    assert_tool_schema,
    collect_tool_stream,
    invoke_tool,
    make_stub_tool,
)
from pirn_agents.tool_decorator import tool


class TestSchemaAssertions(unittest.TestCase):
    def test_assert_tool_schema_passes_on_match(self) -> None:
        stub = make_stub_tool(name="s", parameters_schema={"type": "object", "properties": {}})
        assert_tool_schema(stub, {"type": "object", "properties": {}})

    def test_assert_tool_schema_fails_on_mismatch(self) -> None:
        stub = make_stub_tool(name="s")
        with self.assertRaises(AssertionError):
            assert_tool_schema(stub, {"type": "object", "properties": {}})

    def test_assert_schema_shape_required_and_properties(self) -> None:
        @tool
        async def search(query: str, limit: int = 5) -> str:
            """Search."""
            return query

        assert_schema_shape(
            search,
            required=["query"],
            properties={"query": {"type": "string"}, "limit": {"type": "integer"}},
        )

    def test_assert_schema_shape_wrong_required_fails(self) -> None:
        @tool
        async def search(query: str) -> str:
            """Search."""
            return query

        with self.assertRaises(AssertionError):
            assert_schema_shape(search, required=[])

    def test_assert_schema_shape_missing_property_fails(self) -> None:
        stub = make_stub_tool(name="s")
        with self.assertRaises(AssertionError):
            assert_schema_shape(stub, properties={"absent": {"type": "string"}})

    def test_assert_schema_shape_property_value_mismatch_fails(self) -> None:
        stub = make_stub_tool(name="s")  # input is a string
        with self.assertRaises(AssertionError):
            assert_schema_shape(stub, properties={"input": {"type": "integer"}})


class TestInvocationDrivers(unittest.IsolatedAsyncioTestCase):
    async def test_invoke_tool_sync_and_async(self) -> None:
        @tool
        def sync_tool(x: str) -> str:
            """Sync."""
            return f"sync:{x}"

        @tool
        async def async_tool(x: str) -> str:
            """Async."""
            return f"async:{x}"

        assert await invoke_tool(sync_tool, {"x": "a"}) == "sync:a"
        assert await invoke_tool(async_tool, {"x": "b"}) == "async:b"

    async def test_collect_tool_stream(self) -> None:
        stub = make_stub_tool(name="gen", stream_chunks=["a", "b", "c"])
        assert await collect_tool_stream(stub, {}) == ["a", "b", "c"]

    async def test_collect_stream_on_non_streaming_raises(self) -> None:
        stub = make_stub_tool(name="s")
        with self.assertRaisesRegex(TypeError, "not a streaming tool"):
            await collect_tool_stream(stub, {})


class TestToolTestHarness(unittest.IsolatedAsyncioTestCase):
    def test_rejects_non_tool(self) -> None:
        with self.assertRaisesRegex(TypeError, "Tool"):
            ToolTestHarness("not-a-tool")  # type: ignore[arg-type]

    def test_exposes_wrapped_tool(self) -> None:
        stub = make_stub_tool(name="s")
        assert ToolTestHarness(stub).tool is stub

    async def test_assert_invokes_to_passes(self) -> None:
        harness = ToolTestHarness(make_stub_tool(name="s", result="hi"))
        await harness.assert_invokes_to({"input": "x"}, "hi")

    async def test_assert_invokes_to_fails_on_mismatch(self) -> None:
        harness = ToolTestHarness(make_stub_tool(name="s", result="hi"))
        with self.assertRaises(AssertionError):
            await harness.assert_invokes_to({"input": "x"}, "bye")

    async def test_assert_streams_passes(self) -> None:
        harness = ToolTestHarness(make_stub_tool(name="g", stream_chunks=[1, 2]))
        await harness.assert_streams({}, [1, 2])

    async def test_assert_streams_fails_on_mismatch(self) -> None:
        harness = ToolTestHarness(make_stub_tool(name="g", stream_chunks=[1, 2]))
        with self.assertRaises(AssertionError):
            await harness.assert_streams({}, [1, 2, 3])

    def test_assert_schema_shape_via_harness(self) -> None:
        harness = ToolTestHarness(make_stub_tool(name="s"))
        harness.assert_schema_shape(properties={"input": {"type": "string"}})


if __name__ == "__main__":
    unittest.main()
