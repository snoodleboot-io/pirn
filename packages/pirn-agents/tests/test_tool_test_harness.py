"""Tests for the tool testing kit helpers themselves (S5).

These exercise the kit against :class:`StubTool` fixtures to confirm its
assertions pass on matching tools and fail (raise ``AssertionError``) on
mismatches, and that its drivers handle sync, async, and streaming tools.
"""

from __future__ import annotations

import unittest

from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.testing.tool_test_harness import ToolTestHarness
from pirn_agents.tools.tool_decorator import ToolDecorator


class TestSchemaAssertions(unittest.TestCase):
    def test_assert_tool_schema_passes_on_match(self) -> None:
        stub = StubTool(name="s", parameters_schema={"type": "object", "properties": {}})
        ToolTestHarness.assert_tool_schema(stub, {"type": "object", "properties": {}})

    def test_assert_tool_schema_fails_on_mismatch(self) -> None:
        stub = StubTool(name="s")
        with self.assertRaises(AssertionError):
            ToolTestHarness.assert_tool_schema(stub, {"type": "object", "properties": {}})

    def test_assert_schema_shape_required_and_properties(self) -> None:
        @ToolDecorator.decorate
        async def search(query: str, limit: int = 5) -> str:
            """Search."""
            return query

        ToolTestHarness.assert_tool_schema_shape(
            search,
            required=["query"],
            properties={"query": {"type": "string"}, "limit": {"type": "integer"}},
        )

    def test_assert_schema_shape_wrong_required_fails(self) -> None:
        @ToolDecorator.decorate
        async def search(query: str) -> str:
            """Search."""
            return query

        with self.assertRaises(AssertionError):
            ToolTestHarness.assert_tool_schema_shape(search, required=[])

    def test_assert_schema_shape_missing_property_fails(self) -> None:
        stub = StubTool(name="s")
        with self.assertRaises(AssertionError):
            ToolTestHarness.assert_tool_schema_shape(
                stub, properties={"absent": {"type": "string"}}
            )

    def test_assert_schema_shape_property_value_mismatch_fails(self) -> None:
        stub = StubTool(name="s")  # input is a string
        with self.assertRaises(AssertionError):
            ToolTestHarness.assert_tool_schema_shape(
                stub, properties={"input": {"type": "integer"}}
            )


class TestInvocationDrivers(unittest.IsolatedAsyncioTestCase):
    async def test_invoke_tool_sync_and_async(self) -> None:
        @ToolDecorator.decorate
        def sync_tool(x: str) -> str:
            """Sync."""
            return f"sync:{x}"

        @ToolDecorator.decorate
        async def async_tool(x: str) -> str:
            """Async."""
            return f"async:{x}"

        assert await ToolTestHarness.invoke_tool(sync_tool, {"x": "a"}) == "sync:a"
        assert await ToolTestHarness.invoke_tool(async_tool, {"x": "b"}) == "async:b"

    async def test_collect_tool_stream(self) -> None:
        stub = StubTool(name="gen", stream_chunks=["a", "b", "c"])
        assert await ToolTestHarness.collect_tool_stream(stub, {}) == ["a", "b", "c"]

    async def test_collect_stream_on_non_streaming_raises(self) -> None:
        stub = StubTool(name="s")
        with self.assertRaisesRegex(TypeError, "not a streaming tool"):
            await ToolTestHarness.collect_tool_stream(stub, {})


class TestToolTestHarness(unittest.IsolatedAsyncioTestCase):
    def test_rejects_non_tool(self) -> None:
        with self.assertRaisesRegex(TypeError, "Tool"):
            ToolTestHarness("not-a-tool")  # type: ignore[arg-type]

    def test_exposes_wrapped_tool(self) -> None:
        stub = StubTool(name="s")
        assert ToolTestHarness(stub).tool is stub

    async def test_assert_invokes_to_passes(self) -> None:
        harness = ToolTestHarness(StubTool(name="s", result="hi"))
        await harness.assert_invokes_to({"input": "x"}, "hi")

    async def test_assert_invokes_to_fails_on_mismatch(self) -> None:
        harness = ToolTestHarness(StubTool(name="s", result="hi"))
        with self.assertRaises(AssertionError):
            await harness.assert_invokes_to({"input": "x"}, "bye")

    async def test_assert_streams_passes(self) -> None:
        harness = ToolTestHarness(StubTool(name="g", stream_chunks=[1, 2]))
        await harness.assert_streams({}, [1, 2])

    async def test_assert_streams_fails_on_mismatch(self) -> None:
        harness = ToolTestHarness(StubTool(name="g", stream_chunks=[1, 2]))
        with self.assertRaises(AssertionError):
            await harness.assert_streams({}, [1, 2, 3])

    def test_assert_schema_shape_via_harness(self) -> None:
        harness = ToolTestHarness(StubTool(name="s"))
        harness.assert_schema_shape(properties={"input": {"type": "string"}})


if __name__ == "__main__":
    unittest.main()
