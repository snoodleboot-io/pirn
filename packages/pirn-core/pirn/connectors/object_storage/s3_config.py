"""Configuration dataclass for :class:`S3Store`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import ConnectionConfigDecorator


@ConnectionConfigDecorator.apply(frozen=True)
class S3Config(ConnectionConfig):
    """Configuration for an S3-compatible object store.

    Attributes
    ----------
    bucket:
        Target bucket name (required).
    region:
        AWS region (or S3-compatible region). ``None`` defers to the
        region configured in the environment / AWS config chain.
    endpoint_url:
        Override for S3-compatible endpoints (MinIO, R2, …). ``None`` →
        public AWS.
    access_key_id, secret_access_key, session_token:
        Optional explicit credentials. ``None`` → fall back to the standard
        AWS credential chain.
    multipart_threshold:
        Bytes; bodies larger than this trigger a multipart upload.
    chunk_size:
        Streaming read chunk size.
    """

    bucket: str = ""
    region: str | None = "us-east-1"
    endpoint_url: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None
    multipart_threshold: int = 8 * 1024 * 1024
    chunk_size: int = 1 << 20

    sensitive_fields: ClassVar[tuple[str, ...]] = (
        "access_key_id",
        "secret_access_key",
        "session_token",
    )
