"""Configuration dataclass for :class:`HubSpotClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class HubSpotConfig(ConnectionConfig):
    """Configuration for a HubSpot REST session.

    Attributes
    ----------
    access_token:
        Private-app or OAuth access token (preferred).
    api_key:
        Legacy ``hapikey`` (deprecated by HubSpot, retained for migration).
    """

    access_token: str | None = None
    api_key: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = (
        "access_token",
        "api_key",
    )
