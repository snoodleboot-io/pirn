"""Configuration dataclass for :class:`Neo4jPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class Neo4jConfig(ConnectionConfig):
    """Configuration for a Neo4j async driver connection pool."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_connection_pool_size: int = 50
    connection_timeout: float = 30.0
    encrypted: bool = False

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
