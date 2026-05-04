"""Configuration dataclass for :class:`ArangoDBPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class ArangoDBConfig(ConnectionConfig):
    """Configuration for a python-arango ArangoDB connection."""

    url: str = "http://localhost:8529"
    username: str = "root"
    password: str = ""
    database: str = "_system"
    verify_ssl: bool = True
    connection_timeout: float = 30.0

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
