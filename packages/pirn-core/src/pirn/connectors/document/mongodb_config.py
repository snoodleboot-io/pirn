"""Configuration dataclass for :class:`MongoDBPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class MongoDBConfig(ConnectionConfig):
    """Configuration for a Motor async MongoDB connection.

    Provide ``uri`` (preferred) OR the discrete ``host``/``port``/
    ``username``/``password``/``database`` fields.
    """

    uri: str = "mongodb://localhost:27017"
    host: str = "localhost"
    port: int = 27017
    username: str | None = None
    password: str | None = None
    database: str = ""
    auth_source: str = "admin"
    tls: bool = False
    max_pool_size: int = 100
    server_selection_timeout_ms: int = 5000

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password", "uri")
