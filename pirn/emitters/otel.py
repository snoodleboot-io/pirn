"""OpenTelemetry emitter — emit per-knot trace spans.

Each ``KnotLineage`` record becomes one OTel span with the knot's id
as the span name, the knot class and outcome as attributes, and the
record's start/finish times as the span's timing.

This is observability done right for a pipeline framework: the run is
a parent span, each knot is a child span, and every span carries
enough metadata to filter and group in your tracing UI of choice.

Pair with ``valkey-glide``'s native OTel integration (already
present in our ``valkey-*`` backends) for end-to-end traces from
trigger → knot → ValKey ops → emitter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.emitters.base import Emitter

if TYPE_CHECKING:
    from pirn.core.context import RunResult
    from pirn.core.lineage import KnotLineage
    from pirn.managers.status import StatusEvent


class OpenTelemetryEmitter(Emitter):
    """Emits run events as OpenTelemetry trace spans.

    The emitter doesn't manage span context across the run — each
    lineage record produces an independent span, with the run id as a
    common attribute so a tracing UI can group them.  For nested
    spans (parent run → child knot), wire up an OTel
    ``TracerProvider`` with a sampler that links by ``pirn.run_id``.
    """

    def __init__(self, *, tracer: Any = None) -> None:
        self._tracer = tracer

    def _ensure_tracer(self) -> Any:
        if self._tracer is None:
            try:
                from opentelemetry import trace
            except ImportError as exc:
                raise ImportError(
                    "OpenTelemetryEmitter requires opentelemetry-api; "
                    "install via `pip install pirn[otel]`"
                ) from exc
            self._tracer = trace.get_tracer("pirn")
        return self._tracer

    async def on_status(self, event: StatusEvent) -> None:
        # Status transitions are too noisy for spans (one knot has
        # PENDING → RUNNING → SUCCEEDED).  We use lineage records
        # instead, which represent the *complete* knot execution.
        return

    async def on_lineage(self, record: KnotLineage) -> None:
        tracer = self._ensure_tracer()
        # start_as_current_span is sync; we open and close the span
        # explicitly to honor the lineage record's exact timing.
        span = tracer.start_span(
            f"knot:{record.knot_id}",
            start_time=int(record.started_at.timestamp() * 1e9),
        )
        try:
            span.set_attribute("pirn.run_id", record.run_id)
            span.set_attribute("pirn.knot_id", record.knot_id)
            span.set_attribute("pirn.knot_class", record.knot_class)
            span.set_attribute("pirn.outcome", record.outcome)
            span.set_attribute("pirn.dispatcher", record.dispatcher)
            if record.output_hash:
                span.set_attribute("pirn.output_hash", record.output_hash)
            if record.error_record_id:
                span.set_attribute("pirn.error_record_id", record.error_record_id)
            if record.skip_reason:
                span.set_attribute("pirn.skip_reason", record.skip_reason)
            if record.outcome == "err":
                span.set_status(_otel_status_error())
            elif record.outcome == "skipped":
                span.set_status(_otel_status_unset())
        finally:
            span.end(end_time=int(record.finished_at.timestamp() * 1e9))

    async def on_run_result(self, result: RunResult) -> None:
        tracer = self._ensure_tracer()
        span = tracer.start_span(
            f"run:{result.run_id}",
            start_time=int(result.started_at.timestamp() * 1e9),
        )
        try:
            span.set_attribute("pirn.run_id", result.run_id)
            span.set_attribute("pirn.dispatcher", result.dispatcher)
            span.set_attribute("pirn.succeeded", result.succeeded)
            span.set_attribute(
                "pirn.terminals_requested",
                ",".join(result.terminals_requested),
            )
            if not result.succeeded:
                span.set_status(_otel_status_error())
        finally:
            span.end(end_time=int(result.finished_at.timestamp() * 1e9))


def _otel_status_error() -> Any:
    """Build OTel ``Status(StatusCode.ERROR)`` lazily."""
    from opentelemetry.trace import Status, StatusCode

    return Status(StatusCode.ERROR)


def _otel_status_unset() -> Any:
    """Build OTel ``Status(StatusCode.UNSET)`` lazily."""
    from opentelemetry.trace import Status, StatusCode

    return Status(StatusCode.UNSET)
