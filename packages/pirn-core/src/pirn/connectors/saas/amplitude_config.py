"""Configuration dataclass for :class:`AmplitudeClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class AmplitudeConfig(ConnectionConfig):
    """Configuration for an Amplitude Analytics ingestion session.

    Attributes
    ----------
    api_key:
        Project API key used by the ``amplitude.Amplitude`` ingestion SDK.
    secret_key:
        Project secret key, required by the export / dashboard REST API.
    """

    api_key: str | None = None
    secret_key: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("api_key", "secret_key")
