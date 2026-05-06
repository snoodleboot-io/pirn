"""Configuration dataclass for :class:`MySQLPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class MySQLConfig(ConnectionConfig):
    """Configuration for an aiomysql-based MySQL connection pool.

    Attributes
    ----------
    host / port:
        TCP endpoint of the MySQL server.
    user / password:
        Login credentials.
    database:
        Default database (schema) for the connection session.
    charset:
        Wire charset; ``utf8mb4`` is the safe default for modern MySQL.
    min_size / max_size:
        Pool bounds passed straight through to :func:`aiomysql.create_pool`.
    """

    host: str | None = None
    port: int = 3306
    user: str | None = None
    password: str | None = None
    database: str | None = None
    charset: str = "utf8mb4"
    min_size: int = 1
    max_size: int = 10

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
