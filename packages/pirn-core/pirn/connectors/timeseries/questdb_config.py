"""Configuration dataclass for :class:`QuestDBPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class QuestDBConfig(ConnectionConfig):
    """Configuration for a QuestDB connection pool.

    QuestDB supports three protocols:
    - HTTP REST API on ``http_port`` (9000)
    - InfluxDB Line Protocol ingestion on ``ilp_port`` (9009)
    - PostgreSQL wire protocol on ``pg_port`` (8812)

    This pool uses the PostgreSQL wire protocol via asyncpg.
    """

    host: str = "localhost"
    http_port: int = 9000
    ilp_port: int = 9009
    pg_port: int = 8812
    username: str = "admin"
    password: str = ""
    database: str = "qdb"
    tls: bool = False

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
