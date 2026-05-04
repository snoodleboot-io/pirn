"""Configuration dataclass for :class:`PagerDutyClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class PagerDutyConfig(ConnectionConfig):
    """Configuration for a PagerDuty API session.

    Attributes
    ----------
    api_key:
        PagerDuty REST API key. Required when the client is created from config.
    routing_key:
        Events API v2 routing/integration key for triggering incidents.
    base_url:
        Base URL for the PagerDuty REST API.
    timeout:
        HTTP timeout in seconds.
    """

    api_key: str = ""
    routing_key: str | None = None
    base_url: str = "https://api.pagerduty.com"
    timeout: float = 30.0

    sensitive_fields: ClassVar[tuple[str, ...]] = ("api_key", "routing_key")
