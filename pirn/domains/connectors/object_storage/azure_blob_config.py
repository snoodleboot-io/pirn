"""Configuration dataclass for :class:`AzureBlobStore`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class AzureBlobConfig(ConnectionConfig):
    """Configuration for an Azure Blob Storage object store.

    Either ``connection_string`` (preferred) or the
    ``account_name``/``account_key`` pair must be supplied; the store
    requires a ``container``.

    Attributes
    ----------
    account_name:
        Azure storage account name. Used when ``connection_string`` is
        absent.
    account_key:
        Shared-key credential for ``account_name``.
    connection_string:
        Full Azure connection string. Takes precedence over
        ``account_name``/``account_key`` when set.
    container:
        Target blob container (required).
    chunk_size:
        Streaming read chunk size in bytes.
    """

    account_name: str | None = None
    account_key: str | None = None
    connection_string: str | None = None
    container: str | None = None
    chunk_size: int = 65536

    sensitive_fields: ClassVar[tuple[str, ...]] = (
        "account_key",
        "connection_string",
    )
