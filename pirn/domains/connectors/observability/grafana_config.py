"""Configuration dataclass for :class:`GrafanaClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class GrafanaConfig(ConnectionConfig):
    """Configuration for a Grafana HTTP REST API session.

    Attributes
    ----------
    base_url:
        Grafana base URL (e.g. ``https://grafana.acme.com``). Trailing
        slashes are tolerated.
    api_key:
        Grafana API key or service-account token used as a bearer token.
    """

    base_url: str | None = None
    api_key: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("api_key",)
