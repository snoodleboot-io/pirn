"""Configuration dataclass for :class:`MemgraphPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class MemgraphConfig(ConnectionConfig):
    """Configuration for a Memgraph connection (via gqlalchemy)."""

    host: str = "localhost"
    port: int = 7687
    username: str = ""
    password: str = ""
    database: str = ""
    encrypted: bool = False
    client_name: str = "pirn-memgraph"

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
