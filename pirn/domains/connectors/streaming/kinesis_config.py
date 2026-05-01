"""Configuration dataclass for :class:`KinesisBroker`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class KinesisConfig(ConnectionConfig):
    """Configuration for an aioboto3-backed Kinesis broker."""

    region: str | None = None
    endpoint_url: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None
    stream_arn: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = (
        "access_key_id",
        "secret_access_key",
        "session_token",
    )
