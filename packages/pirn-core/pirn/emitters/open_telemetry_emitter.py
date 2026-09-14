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

from pirn.core.optional_dependency import OptionalDependency
from pirn.emitters.emitter import Emitter

if TYPE_CHECKING:
    from pirn.core.knot_lineage import KnotLineage
    from pirn.core.run_result import RunResult
    from pirn.managers.status_event import StatusEvent


class OpenTelemetryEmitter(Emitter):
    """Emits run events as OpenTelemetry trace spans.

    The emitter doesn't manage span context across the run — each
    lineage record produces an independent span, with the run id as a
    common attribute so a tracing UI can group them.  For nested
    spans (parent run → child knot), wire up an OTel
    ``TracerProvider`` with a sampler that links by ``pirn.run_id``.
    """

    def __init__(self, *, tracer: Any = None) -> None:
        """Initialise the emitter.

        Args:
            tracer: An ``opentelemetry.trace.Tracer`` instance.  When
                ``None`` the tracer is obtained lazily from
                ``opentelemetry.trace.get_tracer("pirn")`` on first use,
                which requires ``opentelemetry-api`` to be installed
                (``pip install "pirn-core[otel]"``).
        """
        self._tracer = tracer

    def _ensure_tracer(self) -> Any:
        """Return the tracer, importing ``opentelemetry-api`` lazily if needed.

        Returns:
            A configured ``opentelemetry.trace.Tracer`` instance.

        Raises:
            ImportError: If ``opentelemetry-api`` is not installed.
        """
        if self._tracer is None:
            trace = OptionalDependency.require("opentelemetry.trace", extra="otel")
            self._tracer = trace.get_tracer("pirn")
        return self._tracer

    async def on_status(self, event: StatusEvent) -> None:
        """No-op for a plain lifecycle transition; a span for a carried event.

        The engine's own per-knot transitions (PENDING → RUNNING →
        SUCCEEDED) are too fine-grained for individual spans and never set
        ``extra`` — those are still ignored, and knot execution timing is
        captured via ``on_lineage`` instead.

        A downstream domain that emits its own ad hoc ``StatusEvent`` for a
        sub-step the engine has no lifecycle for — an LLM call, a tool call,
        a retrieval step inside one knot's ``process()`` — sets ``extra``
        (see ``pirn.managers.status_event.StatusEvent.extra``) to carry
        span-like fields (kind, model, tokens, cost, latency, ...). When
        present, that becomes one short span here: named
        ``"<kind>:<knot_id>"``, stamped with the same ``pirn.run_id`` /
        ``pirn.knot_id`` attributes as every other span this emitter
        produces, plus one ``agents.<key>`` attribute per ``extra`` entry.
        The span's duration is taken from ``extra["latency"]`` (seconds)
        when present, else it is a zero-duration point event at
        ``event.occurred_at``.

        Args:
            event: The status event. Ignored unless ``extra`` is a non-empty
                mapping.
        """
        extra = event.extra if isinstance(getattr(event, "extra", None), dict) else {}
        if not extra:
            return
        tracer = self._ensure_tracer()
        kind = extra.get("kind", "event")
        start_ns = int(event.occurred_at.timestamp() * 1e9)
        span = tracer.start_span(f"{kind}:{event.knot_id}", start_time=start_ns)
        try:
            span.set_attribute("pirn.run_id", event.run_id)
            span.set_attribute("pirn.knot_id", event.knot_id)
            span.set_attribute("pirn.state", event.state.value)
            if event.detail:
                span.set_attribute("pirn.detail", event.detail)
            self._apply_extra_attributes(span, extra)
        finally:
            latency = extra.get("latency")
            end_ns = (
                start_ns + int(latency * 1e9) if isinstance(latency, (int, float)) else start_ns
            )
            span.end(end_time=end_ns)

    @staticmethod
    def _apply_extra_attributes(span: Any, extra: dict[str, Any]) -> None:
        """Copy each ``extra`` entry onto ``span`` as an ``agents.<key>`` attribute.

        Stringifies anything that is not an OTel-primitive attribute type
        (``str``/``bool``/``int``/``float``) rather than rejecting it — the
        caller controls what it puts in ``extra`` and this must never raise.
        """
        for key, value in extra.items():
            attr_key = f"agents.{key}"
            if isinstance(value, (str, bool, int, float)):
                span.set_attribute(attr_key, value)
            else:
                span.set_attribute(attr_key, str(value))

    async def on_lineage(self, record: KnotLineage) -> None:
        """Emits a completed knot execution as an OTel span.

        The span name is ``knot:<knot_id>``.  Timing is set from the
        lineage record's ``started_at`` / ``finished_at`` fields.
        Standard ``pirn.*`` attributes are attached; an error status is
        set when ``outcome == "err"``.

        Args:
            record: The knot lineage record to convert into a span.
        """
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
                span.set_status(self.__status_error())
            elif record.outcome == "skipped":
                span.set_status(self.__status_unset())
        finally:
            span.end(end_time=int(record.finished_at.timestamp() * 1e9))

    async def on_run_result(self, result: RunResult) -> None:
        """Emits the completed run as a top-level OTel span.

        The span name is ``run:<run_id>``.  Timing is set from the
        result's ``started_at`` / ``finished_at`` fields.  An error
        status is set when the run did not succeed.

        Args:
            result: The completed run result to convert into a span.
        """
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
                span.set_status(self.__status_error())
        finally:
            span.end(end_time=int(result.finished_at.timestamp() * 1e9))

    @staticmethod
    def __status_error() -> Any:
        from opentelemetry.trace import Status, StatusCode

        return Status(StatusCode.ERROR)

    @staticmethod
    def __status_unset() -> Any:
        from opentelemetry.trace import Status, StatusCode

        return Status(StatusCode.UNSET)
