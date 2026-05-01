"""OpenTelemetry tracer/emitter wrapper.

Unlike the rest of the observability connectors,
:class:`OpenTelemetryEmitter` is NOT an :class:`ApiClient`. OTel is an
emitter — its calls open spans that the SDK / collector forward to a
backend, not request/response pairs. The lazy import path pulls
``opentelemetry-api`` + ``opentelemetry-sdk`` plus the OTLP exporter,
all installable via the ``pirn[otel]`` extra.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from pirn.domains.connectors.observability.opentelemetry_config import (
    OpenTelemetryConfig,
)


class OpenTelemetryEmitter:
    """Async-friendly wrapper over an OpenTelemetry tracer.

    Tests inject ``tracer=`` directly; production callers pass
    ``config=`` and the tracer is constructed lazily. The wrapper holds a
    minimal API surface (:meth:`emit_span`, :meth:`close`) so the rest of
    pirn does not become coupled to OTel internals.
    """

    def __init__(
        self,
        config: OpenTelemetryConfig | None = None,
        *,
        tracer: Any = None,
    ) -> None:
        if config is None and tracer is None:
            raise TypeError(
                "OpenTelemetryEmitter requires either config= or tracer="
            )
        self._config = config
        self._tracer = tracer
        self._closed = False
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> OpenTelemetryConfig | None:
        return self._config

    async def emit_span(
        self,
        name: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        """Open a span, then close it.

        The span is opened with ``start_as_current_span`` as a context
        manager; entering and exiting the context flushes the span
        through the configured exporter pipeline.
        """
        if not isinstance(name, str) or not name:
            raise ValueError(
                "OpenTelemetryEmitter.emit_span: name must be non-empty"
            )
        tracer = await self._ensure_tracer()
        span_attributes = dict(attributes) if attributes is not None else None
        with tracer.start_as_current_span(name, attributes=span_attributes):
            pass

    async def close(self) -> None:
        """Idempotent shutdown — releases the tracer reference."""
        self._tracer = None
        self._closed = True
        self._logger.debug("opentelemetry.close")

    async def _ensure_tracer(self) -> Any:
        if self._closed:
            raise RuntimeError("OpenTelemetryEmitter is closed")
        if self._tracer is None:
            self._tracer = await self._create_tracer()
        return self._tracer

    async def _create_tracer(self) -> Any:
        try:
            from opentelemetry import trace  # type: ignore[import-not-found]
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import (  # type: ignore[import-not-found]
                Resource,
            )
            from opentelemetry.sdk.trace import (  # type: ignore[import-not-found]
                TracerProvider,
            )
            from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found]
                BatchSpanProcessor,
            )
        except ImportError as exc:
            raise ImportError(
                "OpenTelemetryEmitter requires opentelemetry-api / "
                "opentelemetry-sdk / opentelemetry-exporter-otlp; install "
                "via `pip install pirn[otel]`"
            ) from exc

        if self._config is None:
            raise RuntimeError(
                "OpenTelemetryEmitter: missing config and no injected tracer"
            )

        resource_attrs: dict[str, Any] = {}
        if self._config.service_name is not None:
            resource_attrs["service.name"] = self._config.service_name
        provider = TracerProvider(resource=Resource.create(resource_attrs))

        exporter_kwargs: dict[str, Any] = {}
        if self._config.endpoint is not None:
            exporter_kwargs["endpoint"] = self._config.endpoint
        if self._config.headers is not None:
            exporter_kwargs["headers"] = dict(self._config.headers)
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(**exporter_kwargs))
        )
        trace.set_tracer_provider(provider)
        self._logger.debug("opentelemetry.connect")
        return trace.get_tracer(self._config.service_name or __name__)
