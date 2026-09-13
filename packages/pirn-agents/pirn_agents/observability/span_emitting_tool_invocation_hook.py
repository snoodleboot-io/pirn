"""``SpanEmittingToolInvocationHook`` — bridge F1's tool hook onto the span interface.

.. deprecated:: ADR agents-speaks-core WS4a
    Part of the deprecated Tracer/Span plane; scheduled for deletion after one
    release cycle. A ``ToolInvocation`` knot now reports every engine-scheduled
    tool call through
    :class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`
    on its own, with no hook required; this class still forwards its own
    ``on_finish`` into that recorder (best-effort — see
    :meth:`_forward_to_emitter_path`) for a caller that configured this hook
    on a hand-rolled executor during the deprecation cycle.

This is the seam that makes F1 and F10 observability *one* system rather than
two. F1's :class:`~pirn_agents.tools.tool_invocation_hook.ToolInvocationHook` already
fires ``on_start``/``on_finish`` around every tool call an executor runs; this
subclass turns those callbacks into :class:`Span`\\ s opened on the shared
:class:`~pirn_agents.observability.tracer.Tracer`, so tool spans land in the
same sink as LLM and retrieval spans — no duplicate instrumentation, and the
executor still only knows about the F1 hook interface.
"""

from __future__ import annotations

import asyncio
import warnings

from pirn_agents.observability.agent_call_recorder import AgentCallRecorder
from pirn_agents.observability.span import Span
from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus
from pirn_agents.observability.tracer import Tracer
from pirn_agents.tools.tool_invocation_hook import ToolInvocationHook
from pirn_agents.tools.tool_status import ToolStatus


class SpanEmittingToolInvocationHook(ToolInvocationHook):
    """Emit a TOOL-kind span per invocation via the F1 hook callbacks.

    .. deprecated:: ADR agents-speaks-core WS4a
        See the module docstring.

    ``on_start`` opens a span (correlated by ``call_id``); ``on_finish`` closes
    it with the terminal status and latency. Because the executor swallows hook
    exceptions and the tracer swallows sink exceptions, a misbehaving sink can
    never abort tool execution.
    """

    def __init__(self, tracer: Tracer, *, knot_id: str | None = None) -> None:
        """Bind to the :class:`Tracer` whose sink tool spans are reported to.

        Args:
            tracer: The tracer whose sink these spans are reported to.
            knot_id: Identity of the knot these tool calls run under, stamped on
                every span this hook opens (PIR-798).

                It has to be passed because there is nothing ambient to read:
                core has no ``_current_knot_id`` contextvar, unlike ``run_id``,
                which :class:`Tracer` stamps for itself. An executor that is a
                ``Knot`` can hand over its own ``knot_id``; a caller that is not
                one — ``MapAgent``, for instance — has no knot identity to give
                and leaves this ``None``, in which case the key is omitted
                rather than written as ``None``.

        Raises:
            TypeError: If ``knot_id`` is neither ``None`` nor a ``str``.
        """
        warnings.warn(
            "SpanEmittingToolInvocationHook is deprecated (ADR agents-speaks-core "
            "WS4a) and scheduled for deletion after one release cycle; a "
            "ToolInvocation knot already reports every engine-scheduled tool "
            "call through AgentCallRecorder with no hook required.",
            DeprecationWarning,
            stacklevel=2,
        )
        if knot_id is not None and not isinstance(knot_id, str):
            raise TypeError(
                f"SpanEmittingToolInvocationHook: knot_id must be a str or None, "
                f"got {type(knot_id).__name__}"
            )
        self._tracer = tracer
        self._knot_id = knot_id
        self._open: dict[str, Span] = {}
        # Strong references to the fire-and-forget forwarding tasks
        # `_forward_to_emitter_path` schedules, so Python's GC cannot reclaim
        # them mid-flight (the same concern `EmitterFanout.
        # subscribe_emitters_to_status` documents for its own task list).
        self._pending_tasks: list[asyncio.Task[None]] = []

    def on_start(self, *, tool_name: str, args_digest: str, call_id: str) -> None:
        """Open a TOOL span for the call, keyed by ``call_id``."""
        span = self._tracer.start_span(
            name=f"tool:{tool_name}",
            kind=SpanKind.TOOL,
            attributes=self._span_attributes(
                tool_name=tool_name, args_digest=args_digest, call_id=call_id
            ),
        )
        self._open[call_id] = span

    def _span_attributes(
        self, *, tool_name: str, args_digest: str, call_id: str
    ) -> dict[str, object]:
        """Build the span's attributes, adding ``knot_id`` when one is known.

        ``run_id`` is not added here — :class:`Tracer` stamps it on every span
        it opens, because it is ambient. This method carries only the half that
        is not (PIR-798).
        """
        attributes: dict[str, object] = {
            "tool.name": tool_name,
            "tool.args_digest": args_digest,
            "tool.call_id": call_id,
        }
        if self._knot_id is not None:
            attributes["pirn.knot_id"] = self._knot_id
        return attributes

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
        self._forward_to_emitter_path(
            tool_name=tool_name, call_id=call_id, ok=status is ToolStatus.OK, latency=latency
        )

    def _forward_to_emitter_path(
        self, *, tool_name: str, call_id: str, ok: bool, latency: float
    ) -> None:
        """Best-effort, fire-and-forget forward into ``AgentCallRecorder``.

        ``on_finish`` is a synchronous callback (the F1
        :class:`~pirn_agents.tools.tool_invocation_hook.ToolInvocationHook`
        contract), so it cannot ``await`` the recorder directly; this
        schedules the coroutine as a task on the running loop instead, the
        same bridging shape ``EmitterFanout.subscribe_emitters_to_status``
        uses for the same reason. Silently does nothing when there is no
        ``knot_id`` (nothing to attribute the event to — see ``__init__``)
        or no running loop (a caller invoking the hook outside an event loop
        gets no forwarding, matching how observability has always been
        best-effort here).
        """
        if self._knot_id is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(
            AgentCallRecorder.record(
                knot_id=self._knot_id,
                kind="tool",
                ok=ok,
                latency=latency,
                tool_name=tool_name,
                call_id=call_id,
            )
        )
        self._pending_tasks.append(task)
        self._pending_tasks[:] = [t for t in self._pending_tasks if not t.done()]
