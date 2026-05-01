"""Configuration dataclass for :class:`OpenMetadataClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class OpenMetadataConfig(ConnectionConfig):
    """Configuration for the OpenMetadata REST API.

    Attributes
    ----------
    host_url:
        Base URL of the OpenMetadata server (e.g.
        ``https://open-metadata.acme.com/api``).
    jwt_token:
        Bearer JWT issued from the OpenMetadata UI. Sent in the
        ``Authorization`` header on every request.
    """

    host_url: str | None = None
    jwt_token: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("jwt_token",)
