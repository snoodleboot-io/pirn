"""Configuration dataclass for :class:`PubSubBroker`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class PubSubConfig(ConnectionConfig):
    """Configuration for a Google Pub/Sub broker."""

    project: str | None = None
    service_account_json: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("service_account_json",)
