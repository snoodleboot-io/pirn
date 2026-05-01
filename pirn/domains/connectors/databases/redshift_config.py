"""Configuration dataclass for :class:`RedshiftPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class RedshiftConfig(ConnectionConfig):
    """Configuration for an asyncpg-based Redshift connection pool.

    Redshift speaks the PostgreSQL wire protocol so we reuse asyncpg here.
    Provide ``dsn`` (preferred) OR the discrete fields. ``dsn`` wins when
    both are given.
    """

    dsn: str | None = None
    host: str | None = None
    port: int = 5439
    user: str | None = None
    password: str | None = None
    database: str | None = None
    min_size: int = 1
    max_size: int = 10
    command_timeout: float | None = 30.0
    statement_cache_size: int = 0  # Redshift does not support prepared stmts.

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
