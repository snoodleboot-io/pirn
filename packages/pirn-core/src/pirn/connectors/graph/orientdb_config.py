"""Configuration dataclass for :class:`OrientDBPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class OrientDBConfig(ConnectionConfig):
    """Configuration for an OrientDB connection (via pyorient)."""

    host: str = "localhost"
    port: int = 2424
    http_port: int = 2480
    user: str = "root"
    password: str = ""
    database: str = ""
    server_version: str = ""

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
