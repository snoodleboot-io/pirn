"""Configuration dataclass for :class:`DatadogClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class DatadogConfig(ConnectionConfig):
    """Configuration for a Datadog API session.

    Attributes
    ----------
    api_key:
        Datadog API key (``DD-API-KEY`` header).
    app_key:
        Datadog application key (``DD-APPLICATION-KEY`` header). Required
        for read access to dashboards/monitors and most query endpoints.
    site:
        Datadog site domain (``datadoghq.com``, ``datadoghq.eu``,
        ``us3.datadoghq.com``, ...). Defaults to the US1 site.
    """

    api_key: str | None = None
    app_key: str | None = None
    site: str = "datadoghq.com"

    sensitive_fields: ClassVar[tuple[str, ...]] = ("api_key", "app_key")
