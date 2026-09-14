# pyright: reportUnnecessaryIsInstance=false
# runtime-bound inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""OpenTelemetry tracer/emitter wrapper.

Unlike the rest of the observability connectors,
:class:`OpenTelemetrySpanEmitter` is NOT an :class:`ApiClient`. OTel is an
emitter — its calls open spans that the SDK / collector forward to a
backend, not request/response pairs. The lazy import path pulls
``opentelemetry-api`` + ``opentelemetry-sdk`` plus the OTLP exporter,
all installable via ``pip install "pirn-core[otel]"``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pirn.connectors.observability.opentelemetry_config import (
    OpenTelemetryConfig,
)
from pirn.core.optional_dependency import OptionalDependency
from pirn.exceptions.connector_closed_error import ConnectorClosedError
from pirn.exceptions.connector_config_error import ConnectorConfigError


class OpenTelemetrySpanEmitter:
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
            raise TypeError("OpenTelemetrySpanEmitter requires either config= or tracer=")
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
            raise ValueError("OpenTelemetrySpanEmitter.emit_span: name must be non-empty")
        tracer = await self._ensure_tracer()
        span_attributes = dict(attributes) if attributes is not None else None
        with tracer.start_as_current_span(name, attributes=span_attributes):
            pass

    async def close(self) -> None:
        """Idempotent shutdown — releases the tracer reference."""
        self._tracer = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("opentelemetry.close")

    def _clear_credentials(self) -> None:
        """Drop the in-memory config reference (no inheritance available)."""
        self._config = None

    async def _ensure_tracer(self) -> Any:
        if self._closed:
            raise ConnectorClosedError("OpenTelemetrySpanEmitter is closed")
        if self._tracer is None:
            self._tracer = await self._create_tracer()
        return self._tracer

    async def _create_tracer(self) -> Any:
        trace = OptionalDependency.require("opentelemetry.trace", extra="otel")
        trace_exporter = OptionalDependency.require(
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter", extra="otel"
        )
        resources = OptionalDependency.require("opentelemetry.sdk.resources", extra="otel")
        sdk_trace = OptionalDependency.require("opentelemetry.sdk.trace", extra="otel")
        sdk_trace_export = OptionalDependency.require(
            "opentelemetry.sdk.trace.export", extra="otel"
        )

        if self._config is None:
            raise ConnectorConfigError(
                "OpenTelemetrySpanEmitter: missing config and no injected tracer"
            )

        resource_attrs: dict[str, Any] = {}
        if self._config.service_name is not None:
            resource_attrs["service.name"] = self._config.service_name
        provider = sdk_trace.TracerProvider(resource=resources.Resource.create(resource_attrs))

        exporter_kwargs: dict[str, Any] = {}
        if self._config.endpoint is not None:
            exporter_kwargs["endpoint"] = self._config.endpoint
        if self._config.headers is not None:
            exporter_kwargs["headers"] = dict(self._config.headers)
        provider.add_span_processor(
            sdk_trace_export.BatchSpanProcessor(trace_exporter.OTLPSpanExporter(**exporter_kwargs))
        )
        trace.set_tracer_provider(provider)
        self._logger.debug("opentelemetry.connect")
        return trace.get_tracer(self._config.service_name or __name__)
