"""Configuration dataclass for :class:`DiscordClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class DiscordConfig(ConnectionConfig):
    """Configuration for a Discord webhook/bot session.

    Attributes
    ----------
    webhook_url:
        Incoming webhook URL. Mutually exclusive with ``bot_token`` but
        at least one must be provided when using the client.
    bot_token:
        Bot token for bot-based posting (alternative to ``webhook_url``).
    default_channel_id:
        Default channel ID for bot-based posting.
    timeout:
        HTTP timeout in seconds.
    """

    webhook_url: str = ""
    bot_token: str | None = None
    default_channel_id: str | None = None
    timeout: float = 30.0

    sensitive_fields: ClassVar[tuple[str, ...]] = ("webhook_url", "bot_token")
