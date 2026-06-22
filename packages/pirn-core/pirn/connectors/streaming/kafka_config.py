"""Configuration dataclass for :class:`KafkaBroker`."""

from __future__ import annotations

from dataclasses import field
from typing import Any, ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class KafkaConfig(ConnectionConfig):
    """Configuration for an aiokafka producer / consumer pair."""

    bootstrap_servers: str = "localhost:9092"
    client_id: str = "pirn"
    group_id: str | None = None
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: str | None = None
    sasl_username: str | None = None
    sasl_password: str | None = None
    ssl_cafile: str | None = None
    extra_producer_config: tuple[tuple[str, Any], ...] = field(default_factory=tuple)
    extra_consumer_config: tuple[tuple[str, Any], ...] = field(default_factory=tuple)

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
