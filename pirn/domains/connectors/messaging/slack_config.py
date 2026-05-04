"""Configuration dataclass for :class:`SlackClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class SlackConfig(ConnectionConfig):
    """Configuration for a Slack API session.

    Attributes
    ----------
    bot_token:
        Slack bot token (``xoxb-...``). Required when the client is created
        from config.
    app_token:
        Optional app-level token (``xapp-...``) for Socket Mode.
    default_channel:
        Default channel to post to when no channel is specified.
    timeout:
        HTTP timeout in seconds.
    """

    bot_token: str = ""
    app_token: str | None = None
    default_channel: str = ""
    timeout: float = 30.0

    sensitive_fields: ClassVar[tuple[str, ...]] = ("bot_token", "app_token")
