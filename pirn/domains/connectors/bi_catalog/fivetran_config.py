"""Configuration dataclass for :class:`FivetranClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class FivetranConfig(ConnectionConfig):
    """Configuration for the Fivetran REST API.

    Fivetran authenticates with HTTP Basic auth using a per-account
    ``api_key`` / ``api_secret`` pair issued from the Fivetran dashboard.

    Attributes
    ----------
    api_key:
        Fivetran API key (HTTP Basic username).
    api_secret:
        Fivetran API secret (HTTP Basic password).
    base_url:
        Base URL for the Fivetran REST API. Defaults to the public
        production endpoint.
    """

    api_key: str | None = None
    api_secret: str | None = None
    base_url: str = "https://api.fivetran.com/v1"

    sensitive_fields: ClassVar[tuple[str, ...]] = ("api_key", "api_secret")
