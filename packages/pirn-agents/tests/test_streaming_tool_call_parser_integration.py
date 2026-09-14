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
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.agent.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.testing.stub_tool import StubTool as KitStubTool
from pirn_agents.tools.streaming_tool_call_parser import StreamingToolCallParser
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.toolset import Toolset


def _echo_tool(name: str) -> KitStubTool:
    """A tool that echoes the arguments it was called with."""
    return KitStubTool(
        name=name,
        description=f"echo {name}",
        handler=lambda arguments: {"tool": name, "echo": dict(arguments)},
    )


async def _execute(calls: list[ToolCall], toolset: Toolset) -> tuple[Any, ...]:
    """Run the executor over ``calls`` in a fresh tapestry and return its views."""
    with Tapestry() as t:
        ParallelToolExecutor(tool_calls=calls, toolset=toolset, _config=KnotConfig(id="stcp-int"))
    run = await t.run(RunRequest())
    assert run.succeeded, run.exceptions
    return run.outputs["stcp-int"]


async def test_streamed_calls_execute_through_parallel_executor() -> None:
    async def stream() -> AsyncIterator[Mapping[str, Any]]:
        yield {"index": 0, "id": "c0", "name": "alpha", "arguments": '{"x"'}
        yield {"index": 0, "arguments": ": 1}", "done": True}
        yield {"index": 1, "id": "c1", "name": "beta", "arguments": '{"y": 2}'}
        yield {"index": 1, "done": True, "arguments": ""}

    parser = StreamingToolCallParser()
    toolset = Toolset([_echo_tool("alpha"), _echo_tool("beta")])

    parsed: list[ToolCall] = []
    async for call in parser.parse(stream()):
        parsed.append(call)

    results = await _execute(parsed, toolset)

    assert len(results) == 2
    assert all(r.status == "ok" for r in results)
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
    toolset = Toolset([_echo_tool("alpha"), _echo_tool("beta")])

    dispatched: list[asyncio.Task[tuple[Any, ...]]] = []
    iterator = parser.parse(gated_stream())

    first = await anext(iterator)
    # Dispatch immediately, before draining the rest of the stream.
    dispatched.append(asyncio.create_task(_execute([first], toolset)))
    first_results = await dispatched[0]
    assert not gate.is_set()  # stream still suspended; dispatch already done
    assert len(first_results) == 1
    assert first_results[0].status == "ok"
    assert first_results[0].call_id == "c0"
    assert first_results[0].result == {"tool": "alpha", "echo": {"x": 1}}

    gate.set()
    second = await anext(iterator)
    assert second.call_id == "c1"
