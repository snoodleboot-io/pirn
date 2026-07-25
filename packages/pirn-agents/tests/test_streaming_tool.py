"""Unit tests for the streaming capability facet on the :class:`Tool` base (S2)."""

from __future__ import annotations

import unittest

from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.tool_decorator import tool


@tool
async def counted_stream(n: int) -> str:
    """Yield ``n`` chunks incrementally."""
    for i in range(n):
        yield f"chunk{i}"


class TestFunctionToolStreaming(unittest.IsolatedAsyncioTestCase):
    def test_async_generator_is_streaming(self) -> None:
        assert counted_stream.streaming is True

    def test_plain_tool_is_not_streaming(self) -> None:
        @tool
        async def plain(x: str) -> str:
            """Plain."""
            return x

        assert plain.streaming is False

    async def test_stream_yields_chunks(self) -> None:
        chunks = [c async for c in counted_stream.stream({"n": 3})]
        assert chunks == ["chunk0", "chunk1", "chunk2"]

    async def test_collect_stream_facet(self) -> None:
        assert await counted_stream.collect_stream({"n": 2}) == ["chunk0", "chunk1"]

    async def test_invoke_aggregates_stream_to_list(self) -> None:
        assert await counted_stream.invoke({"n": 2}) == ["chunk0", "chunk1"]

    def test_stream_on_non_streaming_raises(self) -> None:
        @tool
        async def plain(x: str) -> str:
            """Plain."""
            return x

        with self.assertRaisesRegex(TypeError, "not a streaming tool"):
            plain.stream({"x": "1"})


class TestStubToolStreaming(unittest.IsolatedAsyncioTestCase):
    async def test_stub_streams_configured_chunks(self) -> None:
        stub = StubTool(name="s", stream_chunks=["a", "b", "c"])
        assert stub.streaming is True
        assert await stub.collect_stream({}) == ["a", "b", "c"]

    async def test_stub_invoke_aggregates(self) -> None:
        stub = StubTool(name="s", stream_chunks=[1, 2])
        assert await stub.invoke({}) == [1, 2]

    def test_stub_records_stream_invocations(self) -> None:
        stub = StubTool(name="s", stream_chunks=["x"])
        stub.stream({"k": "v"})
        assert stub.stream_invocations == [{"k": "v"}]

    def test_non_streaming_stub_stream_raises(self) -> None:
        stub = StubTool(name="s")
        assert stub.streaming is False
        with self.assertRaisesRegex(TypeError, "not a streaming tool"):
            stub.stream({})


if __name__ == "__main__":
    unittest.main()
