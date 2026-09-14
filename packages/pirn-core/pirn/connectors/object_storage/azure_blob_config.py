"""Configuration dataclass for :class:`AzureBlobStore`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import ConnectionConfigDecorator


@ConnectionConfigDecorator.apply(frozen=True)
class AzureBlobConfig(ConnectionConfig):
    """Configuration for an Azure Blob Storage object store.

    Either ``connection_string`` (preferred), an explicit ``account_url``,
    or the ``account_name``/``account_key`` pair must be supplied; the store
    requires a ``container``.

    Attributes
    ----------
    account_name:
        Azure storage account name. Used when ``connection_string`` and
        ``account_url`` are absent; the endpoint is then
        ``https://{account_name}.blob.core.windows.net``.
    account_key:
        Shared-key credential for ``account_name``.
    connection_string:
        Full Azure connection string. Takes precedence over
        ``account_url`` and ``account_name``/``account_key`` when set.
    account_url:
        Explicit blob-service endpoint (for a sovereign cloud, an emulator or
        a custom domain). Used with ``account_key``, or with a credential
        object passed to the store at construction.
    container:
        Target blob container (required).
    chunk_size:
        Streaming read chunk size in bytes.
    """

    account_name: str | None = None
    account_key: str | None = None
    connection_string: str | None = None
    account_url: str | None = None
    container: str | None = None
    chunk_size: int = 65536

    sensitive_fields: ClassVar[tuple[str, ...]] = (
        "account_key",
        "connection_string",
    )
