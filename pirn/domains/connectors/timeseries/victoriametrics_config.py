"""Configuration dataclass for :class:`VictoriaMetricsPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class VictoriaMetricsConfig(ConnectionConfig):
    """Configuration for a VictoriaMetrics HTTP client.

    VictoriaMetrics exposes Prometheus-compatible HTTP endpoints.
    ``tenant_id`` is used for the cluster edition.
    """

    url: str = "http://localhost:8428"
    username: str | None = None
    password: str | None = None
    tenant_id: str | None = None
    verify_ssl: bool = True
    timeout: float = 30.0

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
