"""Configuration dataclass for :class:`ValkeyStreamBroker`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class ValkeyStreamConfig(ConnectionConfig):
    """Configuration for a Valkey-Streams broker."""

    host: str = "localhost"
    port: int = 6379
    password: str | None = None
    use_tls: bool = False
    consumer_group: str | None = None
    consumer_name: str = "pirn"
    block_ms: int = 1000
    count_per_read: int = 100

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
