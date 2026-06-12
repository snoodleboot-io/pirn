"""Configuration dataclass for :class:`ClickhousePool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class ClickhouseConfig(ConnectionConfig):
    """Configuration for a ClickHouse connection.

    Attributes
    ----------
    host:
        Server hostname or IP.
    port:
        HTTPS interface port (default 8443) or HTTP (8123) — match the
        backend's exposed interface.
    username / password:
        Login credentials.
    database:
        Default database for unqualified table references.
    secure:
        Use TLS (default ``True``) — recommended for any non-local cluster.
    """

    host: str | None = None
    port: int = 8443
    username: str | None = None
    password: str | None = None
    database: str | None = None
    secure: bool = True

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
