"""``AgentCallRecorder`` — the sanctioned way to observe an LLM/tool/retrieval call.

ADR "agents speaks core" (PIR-856, WS4a): agents had a *second* event bus —
:class:`~pirn_agents.observability.tracer.Tracer` opening
:class:`~pirn_agents.observability.span.Span`\\ s against a pluggable
:class:`~pirn_agents.observability.observability_sink.ObservabilitySink` —
entirely disjoint from core's own ``StatusManager``/``Emitter`` stream: a
:class:`~pirn_agents.observability.span.Span` carried no ``run_id``/``knot_id``
of its own (``Tracer`` stamped ``run_id`` on manually; nothing stamped
``knot_id`` because core had no ambient accessor for it), and zero production
code imported ``pirn.emitters`` from anywhere in this package.

This module replaces that second bus with one core-shaped call: build a
``StatusEvent`` whose ``run_id`` comes from :func:`pirn.tapestry.current_run_id`
and whose ``extra`` mapping carries the span-like fields (kind, model, tokens,
cost, latency, ...) an LLM/tool/retrieval call wants to report, then hand it to
:meth:`~pirn.engine.emitter_fanout.EmitterFanout.emit_status`, which delivers it
to the *same* emitter subscription the engine's own per-knot lifecycle
transitions already use (:func:`pirn.tapestry.current_emitters`). One run, one
event stream, one place (``OpenTelemetryEmitter``/``LogEmitter``) that knows how
to render it — see their ``on_status`` for the span/log shape ``extra``
produces.

``Tracer``/``Span``/``ObservabilitySink``/``OtelSink``/``LoggingSink``/
``SpanEmittingToolInvocationHook`` stay importable for one deprecation cycle
(the ADR's public-name rule) and forward into this recorder where a genuine
call site exists; new call sites should use :class:`AgentCallRecorder` directly.
"""

from __future__ import annotations

from typing import Any

from pirn.engine.emitter_fanout import EmitterFanout
from pirn.managers.knot_state import KnotState
from pirn.managers.status_event import StatusEvent
from pirn.tapestry import current_run_id


class AgentCallRecorder:
    """Emits one ``StatusEvent`` per LLM/tool/retrieval call, through core's emitters.

    A call is not one of the engine's own per-knot lifecycle transitions —
    one knot can make several LLM or tool calls inside a single ``process()``
    — so it is reported as its own event, sharing the enclosing knot's
    ``knot_id`` and distinguished from that knot's own PENDING/RUNNING/
    SUCCEEDED/FAILED transitions (and from each other) by ``extra["kind"]``
    plus whatever else the caller supplies (a ``call_id``, a model name, ...).

    Deliberately a single static method rather than a stateful span/context
    object: nothing here needs to nest (no task-local stack to keep balanced
    across a thread hop, unlike the deprecated ``Tracer``), because the
    caller already knows, at the point it calls this, both the outcome and
    the elapsed time — it measured them to build its own result value.
    """

    @staticmethod
    async def record(
        *,
        knot_id: str,
        kind: str,
        ok: bool,
        latency: float,
        detail: str | None = None,
        **extra: Any,
    ) -> None:
        """Emit one call's outcome as a ``StatusEvent`` through the run's emitters.

        A no-op outside a run: :func:`~pirn.tapestry.current_run_id` returns
        ``None`` when no run is in flight, and there is no well-formed run to
        attribute the event to, so nothing is emitted rather than an event
        naming an empty run id. This mirrors the deprecated ``Tracer``'s
        "zero-cost until a run is actually happening" default.

        Args:
            knot_id: The enclosing knot's ``knot_id``. Never ambient — core
                deliberately has no ``current_knot_id()`` companion to
                ``current_run_id()`` (see that accessor's docstring), so
                every call site supplies its own, the same way a ``Knot``
                reads ``self.knot_id``.
            kind: Short call-site kind, e.g. ``"llm"``, ``"tool"``,
                ``"retrieval"``. Stamped into ``extra["kind"]``; consumed by
                ``OpenTelemetryEmitter.on_status`` to name the span.
            ok: Whether the call succeeded. Maps to
                ``KnotState.SUCCEEDED``/``KnotState.FAILED`` — this is a
                terminal, already-happened call, never ``PENDING``/
                ``RUNNING``/``SKIPPED``.
            latency: Wall-clock duration of the call, in seconds. Stamped
                into ``extra["latency"]``, which ``OpenTelemetryEmitter``
                uses as the rendered span's duration.
            detail: Optional short human-readable summary (e.g. an error
                message on failure).
            **extra: Additional span-like fields — ``model``, ``tokens``,
                ``cost``, a ``call_id``, and the like — merged with ``kind``
                and ``latency`` into the event's ``extra`` mapping.
        """
        run_id = current_run_id()
        if run_id is None:
            return
        event = StatusEvent(
            run_id=run_id,
            knot_id=knot_id,
            state=KnotState.SUCCEEDED if ok else KnotState.FAILED,
            detail=detail,
            extra={"kind": kind, "latency": latency, **extra},
        )
        await EmitterFanout.emit_status(event)
