"""Configuration dataclass for :class:`PrometheusClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class PrometheusConfig(ConnectionConfig):
    """Configuration for a Prometheus HTTP query API session.

    Attributes
    ----------
    base_url:
        Prometheus server base URL (e.g. ``http://prometheus:9090``).
        Trailing slashes are tolerated.
    bearer_token:
        Optional bearer token sent as ``Authorization: Bearer <token>``
        for Prometheus deployments fronted by an auth proxy.
    """

    base_url: str | None = None
    bearer_token: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("bearer_token",)
