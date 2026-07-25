"""Tests that F1's tool hook integrates with the F10 span interface (PIR-311).

Wires :class:`SpanEmittingToolInvocationHook` into the real
:class:`ParallelToolExecutor` so the executor's existing per-call hook seam
emits TOOL spans into the shared sink — no duplicate instrumentation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.observability.span_emitting_tool_invocation_hook import (
    SpanEmittingToolInvocationHook,
)
from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus
from pirn_agents.observability.tracer import Tracer
from pirn_agents.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.tool import Tool
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus
from tests.observability._recording_sink import RecordingSink


class _EchoTool(Tool):
    def __init__(self, *, name: str, boom: bool = False) -> None:
        self._name = name
        self._boom = boom

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "echo"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        if self._boom:
            raise RuntimeError("tool failed")
        return self._name


def _executor(hook: SpanEmittingToolInvocationHook) -> ParallelToolExecutor:
    with Tapestry():
        return ParallelToolExecutor(
            tool_calls=[],
            toolset=Toolset(),
            hook=hook,
            _config=KnotConfig(id="pte-obs", validate_io=False),
        )


class TestHookAdapter:
    async def test_ok_call_emits_ok_tool_span(self) -> None:
        sink = RecordingSink()
        hook = SpanEmittingToolInvocationHook(Tracer(sink))
        executor = _executor(hook)

        toolset = Toolset([_EchoTool(name="search")])
        results = await executor.process(
            tool_calls=[ToolCall(tool_name="search", arguments={}, call_id="c1")],
            toolset=toolset,
            max_concurrency=1,
            timeout=None,
            retries=0,
        )
        assert results[0].status is ToolStatus.OK
        assert len(sink.finished) == 1
        span = sink.finished[0]
        assert span.kind is SpanKind.TOOL
        assert span.status is SpanStatus.OK
        assert span.attributes["tool.name"] == "search"
        assert span.attributes["tool.call_id"] == "c1"
        assert "tool.latency_s" in span.attributes

    async def test_failed_call_emits_error_tool_span(self) -> None:
        sink = RecordingSink()
        hook = SpanEmittingToolInvocationHook(Tracer(sink))
        executor = _executor(hook)

        toolset = Toolset([_EchoTool(name="boom", boom=True)])
        results = await executor.process(
            tool_calls=[ToolCall(tool_name="boom", arguments={}, call_id="c2")],
            toolset=toolset,
            max_concurrency=1,
            timeout=None,
            retries=0,
        )
        assert results[0].status is ToolStatus.ERROR
        assert sink.finished[0].status is SpanStatus.ERROR

    async def test_unknown_call_id_finish_is_ignored(self) -> None:
        hook = SpanEmittingToolInvocationHook(Tracer(RecordingSink()))
        # No matching on_start; must not raise.
        hook.on_finish(tool_name="x", call_id="missing", status=ToolStatus.OK, latency=0.1)
