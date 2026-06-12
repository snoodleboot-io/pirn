"""Configuration dataclass for :class:`RabbitMQBroker`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class RabbitMQConfig(ConnectionConfig):
    """Configuration for an aio-pika RabbitMQ broker."""

    host: str = "localhost"
    port: int = 5672
    user: str | None = None
    password: str | None = None
    vhost: str = "/"
    ssl: bool = False

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
