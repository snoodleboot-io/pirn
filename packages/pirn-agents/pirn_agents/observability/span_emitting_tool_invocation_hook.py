"""``SpanEmittingToolInvocationHook`` — bridge F1's tool hook onto the span interface.

This is the seam that makes F1 and F10 observability *one* system rather than
two. F1's :class:`~pirn_agents.tool_invocation_hook.ToolInvocationHook` already
fires ``on_start``/``on_finish`` around every tool call an executor runs; this
subclass turns those callbacks into :class:`Span`\\ s opened on the shared
:class:`~pirn_agents.observability.tracer.Tracer`, so tool spans land in the
same sink as LLM and retrieval spans — no duplicate instrumentation, and the
executor still only knows about the F1 hook interface.
"""

from __future__ import annotations

from pirn_agents.observability.span import Span
from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus
from pirn_agents.observability.tracer import Tracer
from pirn_agents.tool_invocation_hook import ToolInvocationHook
from pirn_agents.types.tool_status import ToolStatus


class SpanEmittingToolInvocationHook(ToolInvocationHook):
    """Emit a TOOL-kind span per invocation via the F1 hook callbacks.

    ``on_start`` opens a span (correlated by ``call_id``); ``on_finish`` closes
    it with the terminal status and latency. Because the executor swallows hook
    exceptions and the tracer swallows sink exceptions, a misbehaving sink can
    never abort tool execution.
    """

    def __init__(self, tracer: Tracer) -> None:
        """Bind to the :class:`Tracer` whose sink tool spans are reported to."""
        self._tracer = tracer
        self._open: dict[str, Span] = {}

    def on_start(self, *, tool_name: str, args_digest: str, call_id: str) -> None:
        """Open a TOOL span for the call, keyed by ``call_id``."""
        span = self._tracer.start_span(
            name=f"tool:{tool_name}",
            kind=SpanKind.TOOL,
            attributes={
                "tool.name": tool_name,
                "tool.args_digest": args_digest,
                "tool.call_id": call_id,
            },
        )
        self._open[call_id] = span

    def on_finish(
        self, *, tool_name: str, call_id: str, status: ToolStatus, latency: float
    ) -> None:
        """Close the span opened for ``call_id`` with status and latency."""
        span = self._open.pop(call_id, None)
        if span is None:
            return
        span.set_attribute("tool.status", status.value)
        span.set_attribute("tool.latency_s", latency)
        span.finish(SpanStatus.OK if status is ToolStatus.OK else SpanStatus.ERROR)
