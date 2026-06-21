"""Configuration dataclass for :class:`CouchDBPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class CouchDBConfig(ConnectionConfig):
    """Configuration for an aiocouch async CouchDB connection."""

    url: str = "http://localhost:5984"
    username: str = "admin"
    password: str = ""
    database: str = ""
    verify_ssl: bool = True

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
