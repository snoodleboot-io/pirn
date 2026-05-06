"""Configuration dataclass for :class:`DataHubClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class DataHubConfig(ConnectionConfig):
    """Configuration for the DataHub REST and GraphQL endpoints.

    Attributes
    ----------
    gms_url:
        URL of the DataHub Generalised Metadata Store (GMS) — the
        DataHub backend that exposes both REST and GraphQL surfaces.
    token:
        Optional personal access token used as a bearer token in the
        ``Authorization`` header.
    """

    gms_url: str | None = None
    token: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("token",)
