"""Structured span/callback observability with a pluggable, no-op-default sink.

Generalises F1's per-tool-call
:class:`~pirn_agents.tool_invocation_hook.ToolInvocationHook` into a broader
span interface that wraps LLM calls, tool invocations, and retrievals alike. A
:class:`~pirn_agents.observability.tracer.Tracer` starts and finishes
:class:`~pirn_agents.observability.span.Span`\\ s and reports them to a
pluggable :class:`~pirn_agents.observability.observability_sink.ObservabilitySink`
that defaults to a genuine no-op (zero required backend). Concrete sinks — a
stdlib :class:`~pirn_agents.observability.logging_sink.LoggingSink` and an
OTel-style :class:`~pirn_agents.observability.otel_sink.OtelSink` behind the
lazy ``otel`` extra — plug in without the core importing any backend. The F1
tool hook re-enters this interface via
:class:`~pirn_agents.observability.span_emitting_tool_invocation_hook.SpanEmittingToolInvocationHook`
so instrumentation is never duplicated.
"""

__all__: list[str] = []
