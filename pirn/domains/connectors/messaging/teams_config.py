"""Configuration dataclass for :class:`TeamsClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class TeamsConfig(ConnectionConfig):
    """Configuration for a Microsoft Teams incoming webhook session.

    Attributes
    ----------
    webhook_url:
        Incoming webhook URL. Required when the client is created from config.
    timeout:
        HTTP timeout in seconds.
    """

    webhook_url: str = ""
    timeout: float = 30.0

    sensitive_fields: ClassVar[tuple[str, ...]] = ("webhook_url",)
