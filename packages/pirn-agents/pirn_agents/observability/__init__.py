"""Agent-call observability through core's own event stream (ADR agents-speaks-core WS4a).

Every LLM/tool/retrieval call site reports through
:class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`,
which emits a core ``StatusEvent`` — ``run_id``/``knot_id`` sourced from the
run itself, ``extra`` carrying whatever span-like fields the call wants to
report (``kind``, ``model``, ``tokens``, ``cost``, ``latency``, …) — through
the run's own emitters (``pirn.emitters.log_emitter.LogEmitter``,
``pirn.emitters.open_telemetry_emitter.OpenTelemetryEmitter``, or any custom
:class:`~pirn.emitters.emitter.Emitter`). There is no separate sink to plug
in and nothing to subclass: instrumentation is automatic the moment a call
runs inside a ``Tapestry``.
"""

__all__: list[str] = []
