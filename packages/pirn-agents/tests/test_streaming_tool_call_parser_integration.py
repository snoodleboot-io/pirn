"""Integration: feed streamed, incrementally-parsed calls into the
:class:`ParallelToolExecutor`.

This exercises the F1-S6 → F1-S3 seam: as :class:`StreamingToolCallParser`
yields each :class:`ToolCall`, the test dispatches it against a real
:class:`Toolset`/:class:`ParallelToolExecutor` pair. It asserts that (a) two
complete calls round-trip to two OK :class:`ToolResult`s with matching
call ids, and (b) dispatch can begin as soon as the first call is parsed —
before the delta stream has finished.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.streaming_tool_call_parser import StreamingToolCallParser
from pirn_agents.tool import Tool
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus


class StubTool(Tool):
    """A tool that echoes the arguments it was invoked with."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"echo {self._name}"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        return {"tool": self._name, "echo": dict(arguments)}


def _make_executor() -> ParallelToolExecutor:
    """Build an executor inside a throwaway tapestry context."""
    with Tapestry():
        return ParallelToolExecutor(
            tool_calls=[],
            toolset=Toolset(),
            _config=KnotConfig(id="stcp-int", validate_io=False),
        )


async def test_streamed_calls_execute_through_parallel_executor() -> None:
    async def stream() -> AsyncIterator[Mapping[str, Any]]:
        yield {"index": 0, "id": "c0", "name": "alpha", "arguments": '{"x"'}
        yield {"index": 0, "arguments": ": 1}", "done": True}
        yield {"index": 1, "id": "c1", "name": "beta", "arguments": '{"y": 2}'}
        yield {"index": 1, "done": True, "arguments": ""}

    parser = StreamingToolCallParser()
    toolset = Toolset([StubTool("alpha"), StubTool("beta")])

    parsed: list[ToolCall] = []
    async for call in parser.parse(stream()):
        parsed.append(call)

    executor = _make_executor()
    results = await executor.process(
        tool_calls=parsed,
        toolset=toolset,
        max_concurrency=8,
        timeout=None,
        retries=0,
    )

    assert len(results) == 2
    assert all(r.status is ToolStatus.OK for r in results)
    by_id = {r.call_id: r for r in results}
    assert by_id["c0"].result == {"tool": "alpha", "echo": {"x": 1}}
    assert by_id["c1"].result == {"tool": "beta", "echo": {"y": 2}}


async def test_dispatch_starts_before_stream_completes() -> None:
    # Prove the "start dispatch early" property: index 0's task is created and
    # awaited to completion while the delta stream is still blocked on a gate,
    # i.e. index 1 has not yet been produced.
    gate = asyncio.Event()

    async def gated_stream() -> AsyncIterator[Mapping[str, Any]]:
        yield {"index": 0, "id": "c0", "name": "alpha", "arguments": '{"x": 1}', "done": True}
        await gate.wait()
        yield {"index": 1, "id": "c1", "name": "beta", "arguments": '{"y": 2}', "done": True}

    parser = StreamingToolCallParser()
    toolset = Toolset([StubTool("alpha"), StubTool("beta")])
    executor = _make_executor()

    dispatched: list[asyncio.Task[tuple[Any, ...]]] = []
    iterator = parser.parse(gated_stream())

    first = await anext(iterator)
    # Dispatch immediately, before draining the rest of the stream.
    dispatched.append(
        asyncio.create_task(
            executor.process(
                tool_calls=[first],
                toolset=toolset,
                max_concurrency=8,
                timeout=None,
                retries=0,
            )
        )
    )
    first_results = await dispatched[0]
    assert not gate.is_set()  # stream still suspended; dispatch already done
    assert len(first_results) == 1
    assert first_results[0].status is ToolStatus.OK
    assert first_results[0].call_id == "c0"
    assert first_results[0].result == {"tool": "alpha", "echo": {"x": 1}}

    gate.set()
    second = await anext(iterator)
    assert second.call_id == "c1"
