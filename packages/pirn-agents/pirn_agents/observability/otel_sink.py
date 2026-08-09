"""``OtelSink`` — an OpenTelemetry-backed :class:`ObservabilitySink` behind a lazy extra.

The one sink that needs a real backend. ``opentelemetry`` is imported lazily
via :func:`pirn_agents._internal._require._require` at construction time, so ``import
pirn_agents`` — and importing this very module — stays backend-free; only
*constructing* an :class:`OtelSink` requires the ``otel`` extra. Each pirn
:class:`Span` is mapped onto an OTel span on finish, carrying its kind, status,
attributes, and duration.

Span attributes are redacted on the way out. Nothing constrains what a knot puts
in them and this sink ships them to a *third-party collector*, so a
:class:`~pirn_agents.security.secret_redactor.SecretRedactor` — the same scanner
PIR-725 attached to
:class:`~pirn_agents.observability.logging_sink.LoggingSink`, not a second set
of patterns — runs over the mapping first, and again over the ``repr`` of every
non-primitive (PIR-789).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents._internal._require import _require
from pirn_agents.observability.observability_sink import ObservabilitySink
from pirn_agents.observability.span import Span
from pirn_agents.observability.span_status import SpanStatus
from pirn_agents.security.secret_redactor import SecretRedactor


class OtelSink(ObservabilitySink):
    """Export pirn spans to an OpenTelemetry tracer, redacting secrets.

    Construction lazily imports ``opentelemetry``; without the ``otel`` extra
    installed a friendly :class:`ImportError` naming the install command is
    raised. A caller may inject an OTel tracer; otherwise the global tracer is
    used.
    """

    def __init__(
        self,
        tracer: Any | None = None,
        *,
        redactor: SecretRedactor | None = None,
        redact_secrets: bool = True,
    ) -> None:
        """Resolve an OTel tracer, importing the backend lazily.

        Args:
            tracer: An OpenTelemetry ``Tracer`` to export to; when ``None`` the
                globally configured tracer (``opentelemetry.trace.get_tracer``)
                is used.
            redactor: The redactor attribute values are scrubbed through; a
                default one is built when ``None``. Inject to widen the pattern
                set or the secret-bearing key names.
            redact_secrets: Set ``False`` to export attributes verbatim — only
                when something upstream already redacts, or the collector is as
                trusted as the process itself.

        Raises:
            ImportError: If the ``otel`` extra (``opentelemetry``) is not
                installed.
            TypeError: If ``redactor`` is not a :class:`SecretRedactor`.
        """
        if redactor is not None and not isinstance(redactor, SecretRedactor):
            raise TypeError("OtelSink: redactor must be a SecretRedactor")
        otel_trace = _require("otel", "opentelemetry.trace")
        self._otel_trace = otel_trace
        self._tracer = tracer if tracer is not None else otel_trace.get_tracer("pirn_agents")
        if not redact_secrets:
            self._redactor: SecretRedactor | None = None
        else:
            self._redactor = redactor if redactor is not None else SecretRedactor()

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
            self._apply_attributes(otel_span, self._redact(span.attributes))
            if span.status is SpanStatus.ERROR:
                status_cls = self._otel_trace.Status
                otel_span.set_status(status_cls(self._otel_trace.StatusCode.ERROR))
        finally:
            otel_span.end()

    def _redact(self, attributes: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return ``attributes`` with secrets scrubbed out of every leaf.

        Delegates the whole walk to
        :meth:`~pirn_agents.security.secret_redactor.SecretRedactor.redact_arguments`,
        which returns a structural copy — the span's own attributes are never
        mutated, so a second sink still sees what the knot recorded.
        """
        if self._redactor is None:
            return attributes
        return self._redactor.redact_arguments(attributes).value

    def _apply_attributes(self, otel_span: Any, attributes: Mapping[str, Any]) -> None:
        """Copy pirn span attributes onto an OTel span, stringifying odd types.

        The ``repr`` of a non-primitive is redacted *after* stringification: the
        structural walk cannot see inside an opaque object, and a client handle
        whose ``repr`` embeds its DSN is the likeliest way a credential reaches
        a collector.
        """
        for key, value in attributes.items():
            if isinstance(value, (str, bool, int, float)):
                otel_span.set_attribute(key, value)
            else:
                otel_span.set_attribute(key, self._redact_repr(value))

    def _redact_repr(self, value: Any) -> str:
        """Return ``repr(value)`` with any secret it embeds scrubbed."""
        rendered = repr(value)
        if self._redactor is None:
            return rendered
        return str(self._redactor.redact_text(rendered).value)
