"""Configuration dataclass for :class:`TelegramClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


_VALID_PARSE_MODES: frozenset[str] = frozenset({"HTML", "Markdown", "MarkdownV2"})


@connection_config(frozen=True)
class TelegramConfig(ConnectionConfig):
    """Configuration for a Telegram Bot API session.

    Attributes
    ----------
    bot_token:
        Telegram bot token (``123456:ABC-DEF1234...``). Required when
        the client is created from config.
    default_chat_id:
        Default chat or channel ID for messages.
    parse_mode:
        Default parse mode for message formatting. Must be one of
        ``"HTML"``, ``"Markdown"``, ``"MarkdownV2"``.
    timeout:
        HTTP timeout in seconds.
    """

    bot_token: str = ""
    default_chat_id: str | int | None = None
    parse_mode: str = "HTML"
    timeout: float = 30.0

    sensitive_fields: ClassVar[tuple[str, ...]] = ("bot_token",)

    def __post_init__(self) -> None:
        if self.parse_mode not in _VALID_PARSE_MODES:
            raise ValueError(
                f"TelegramConfig: parse_mode must be one of "
                f"{sorted(_VALID_PARSE_MODES)!r}; got {self.parse_mode!r}"
            )
