"""Configuration dataclass for :class:`PostgresPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class PostgresConfig(ConnectionConfig):
    """Configuration for an asyncpg connection pool.

    Provide ``dsn`` (preferred) OR the discrete ``host``/``port``/``user``/
    ``password``/``database`` fields. ``dsn`` wins when both are given.
    """

    dsn: str | None = None
    host: str | None = None
    port: int = 5432
    user: str | None = None
    password: str | None = None
    database: str | None = None
    min_size: int = 1
    max_size: int = 10
    command_timeout: float | None = 30.0
    statement_cache_size: int = 100

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
