"""Configuration dataclass for :class:`AirbyteClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class AirbyteConfig(ConnectionConfig):
    """Configuration for the Airbyte REST API.

    Airbyte Cloud authenticates via OAuth2 client-credentials. Either
    provide ``client_id`` / ``client_secret`` (the connector exchanges
    them for an access token) or pass a previously-issued
    ``access_token`` directly for short-lived sessions.

    Attributes
    ----------
    base_url:
        Base URL for the Airbyte REST API. Defaults to the public
        Airbyte Cloud endpoint.
    client_id:
        OAuth2 client ID issued from the Airbyte workspace.
    client_secret:
        OAuth2 client secret paired with ``client_id``.
    access_token:
        Pre-fetched bearer token; used directly when present.
    """

    base_url: str = "https://api.airbyte.com/v1"
    client_id: str | None = None
    client_secret: str | None = None
    access_token: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = (
        "client_secret",
        "access_token",
    )
