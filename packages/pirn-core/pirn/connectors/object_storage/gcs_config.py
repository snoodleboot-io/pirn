"""Configuration dataclass for :class:`GCSStore`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class GCSConfig(ConnectionConfig):
    """Configuration for a Google Cloud Storage object store.

    Attributes
    ----------
    bucket:
        Target bucket name (required).
    service_account_json:
        Filesystem path to a Google service-account JSON key file. ``None``
        falls back to Application Default Credentials.
    project:
        Google Cloud project ID. ``None`` allows the underlying client to
        infer it from the credentials.
    chunk_size:
        Streaming read chunk size in bytes.
    """

    bucket: str | None = None
    service_account_json: str | None = None
    project: str | None = None
    chunk_size: int = 65536

    sensitive_fields: ClassVar[tuple[str, ...]] = ("service_account_json",)
