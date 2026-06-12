"""Configuration dataclass for :class:`TimescaleDBPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class TimescaleDBConfig(ConnectionConfig):
    """Configuration for a TimescaleDB (PostgreSQL extension) connection pool.

    TimescaleDB uses the standard PostgreSQL wire protocol. Provide ``dsn``
    (preferred) OR the discrete connection fields. ``dsn`` wins when both are
    given. ``schema`` sets the ``search_path`` on the connection.
    """

    dsn: str | None = None
    host: str = "localhost"
    port: int = 5432
    user: str | None = None
    password: str | None = None
    database: str | None = None
    schema: str = "public"
    min_size: int = 1
    max_size: int = 10
    command_timeout: float | None = 30.0

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
