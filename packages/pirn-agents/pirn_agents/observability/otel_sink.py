"""``OtelSink`` — an OpenTelemetry-backed :class:`ObservabilitySink` behind a lazy extra.

The one sink that needs a real backend. ``opentelemetry`` is imported lazily
via :func:`pirn_agents._require._require` at construction time, so ``import
pirn_agents`` — and importing this very module — stays backend-free; only
*constructing* an :class:`OtelSink` requires the ``otel`` extra. Each pirn
:class:`Span` is mapped onto an OTel span on finish, carrying its kind, status,
attributes, and duration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents._require import _require
from pirn_agents.observability.observability_sink import ObservabilitySink
from pirn_agents.observability.span import Span
from pirn_agents.observability.span_status import SpanStatus


class OtelSink(ObservabilitySink):
    """Export pirn spans to an OpenTelemetry tracer.

    Construction lazily imports ``opentelemetry``; without the ``otel`` extra
    installed a friendly :class:`ImportError` naming the install command is
    raised. A caller may inject an OTel tracer; otherwise the global tracer is
    used.
    """

    def __init__(self, tracer: Any | None = None) -> None:
        """Resolve an OTel tracer, importing the backend lazily.

        Args:
            tracer: An OpenTelemetry ``Tracer`` to export to; when ``None`` the
                globally configured tracer (``opentelemetry.trace.get_tracer``)
                is used.

        Raises:
            ImportError: If the ``otel`` extra (``opentelemetry``) is not
                installed.
        """
        otel_trace = _require("otel", "opentelemetry.trace")
        self._otel_trace = otel_trace
        self._tracer = tracer if tracer is not None else otel_trace.get_tracer("pirn_agents")

    def on_finish(self, span: Span) -> None:
        """Emit a completed OTel span mirroring the pirn ``span``.

        Modelled on span *finish* (rather than start) so the OTel span is
        created and ended in one shot with the full attribute set and duration
        known — the common shape for exporting already-timed regions.
        """
        otel_span = self._tracer.start_span(span.name)
        try:
            otel_span.set_attribute("pirn.span.kind", span.kind.value)
            otel_span.set_attribute("pirn.span.status", span.status.value)
            if span.duration is not None:
                otel_span.set_attribute("pirn.span.duration_s", span.duration)
            self._apply_attributes(otel_span, span.attributes)
            if span.status is SpanStatus.ERROR:
                status_cls = self._otel_trace.Status
                otel_span.set_status(status_cls(self._otel_trace.StatusCode.ERROR))
        finally:
            otel_span.end()

    @staticmethod
    def _apply_attributes(otel_span: Any, attributes: Mapping[str, Any]) -> None:
        """Copy pirn span attributes onto an OTel span, stringifying odd types."""
        for key, value in attributes.items():
            if isinstance(value, (str, bool, int, float)):
                otel_span.set_attribute(key, value)
            else:
                otel_span.set_attribute(key, repr(value))
