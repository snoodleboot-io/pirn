"""Configuration dataclass for :class:`OpenTelemetryEmitter`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class OpenTelemetryConfig(ConnectionConfig):
    """Configuration for an OpenTelemetry tracer/emitter.

    Attributes
    ----------
    service_name:
        Logical service name attached to emitted spans.
    endpoint:
        OTLP exporter endpoint URL (e.g.
        ``http://otel-collector:4317``). When ``None`` the OTel SDK uses
        its environment-driven defaults.
    headers:
        OTLP exporter headers. Authentication tokens (e.g. ``Bearer
        <token>``) MUST be redacted at the call site before logging — the
        ``headers`` field as a whole is not flagged as sensitive because
        its sensitivity is per-key, but callers should treat it as
        credential-bearing if they put bearer tokens there.

    Notes
    -----
    ``sensitive_fields`` is intentionally empty. The ``headers`` field is
    a free-form mapping; if it carries auth material the caller is
    responsible for not logging it.
    """

    service_name: str | None = None
    endpoint: str | None = None
    headers: dict[str, str] | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
