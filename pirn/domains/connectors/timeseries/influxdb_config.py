"""Configuration dataclass for :class:`InfluxDBPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class InfluxDBConfig(ConnectionConfig):
    """Configuration for an InfluxDB async client.

    ``org`` and ``bucket`` are required (must be non-empty).
    ``token`` is the InfluxDB auth token and is treated as sensitive.
    """

    url: str = "http://localhost:8086"
    token: str = ""
    org: str = ""
    bucket: str = ""
    timeout: int = 10_000
    verify_ssl: bool = True

    sensitive_fields: ClassVar[tuple[str, ...]] = ("token",)

    def __post_init__(self) -> None:
        if not self.org:
            raise ValueError("InfluxDBConfig: 'org' must be non-empty")
        if not self.bucket:
            raise ValueError("InfluxDBConfig: 'bucket' must be non-empty")
