"""Configuration dataclass for :class:`CouchbasePool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class CouchbaseConfig(ConnectionConfig):
    """Configuration for a Couchbase SDK connection.

    ``bucket`` is required and must be non-empty.
    """

    connection_string: str = "couchbase://localhost"
    username: str = ""
    password: str = ""
    bucket: str = ""
    scope: str = "_default"
    collection: str = "_default"
    kv_timeout_ms: int = 2500
    query_timeout_ms: int = 75000

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)

    def __post_init__(self) -> None:
        if not self.bucket:
            raise ValueError("CouchbaseConfig: bucket must be non-empty")
