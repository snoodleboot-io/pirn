"""Azure Blob Storage ``DataStore``.

Values are cloudpickled and stored as Azure Blob objects keyed by
content hash.  Suitable for Azure-hosted deployments.

Requires the ``azure-storage-blob`` package::

    pip install pirn[azure]

Construction accepts a connection string or an account URL with a
credential.  An optional pre-built ``BlobServiceClient`` can be passed
directly for testing.  The store composes over
:class:`~pirn.connectors.object_storage.azure_blob_store.AzureBlobStore`,
which opens one service client on first use and holds it until
:meth:`~pirn.backends.base.data_store.DataStore.close` (PIR-869).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.backends._signer import _Signer
from pirn.backends.base._cloud_object_store import _CloudObjectStore

if TYPE_CHECKING:
    from pirn.connectors.object_store import ObjectStore


class AzureBlobDataStore(_CloudObjectStore):
    """``DataStore`` backed by Azure Blob Storage.

    Each value is one blob at ``{container}/{prefix}{hash}``.
    Use Azure Blob lifecycle management policies for time-based scrubbing
    in production; ``scrub()`` deletes immediately for explicit removal.
    """

    def __init__(
        self,
        *,
        container: str,
        prefix: str = "pirn/data/",
        connection_string: str | None = None,
        account_url: str | None = None,
        credential: Any = None,
        client: Any = None,
        signer: _Signer | None = None,
        allow_unsigned: bool = False,
    ) -> None:
        """Initialise the store.

        Args:
            container: Name of the blob container to use.
            prefix: Key prefix for all blobs written by this store.
            connection_string: Full Azure connection string.  Takes
                precedence over ``account_url``/``credential``.
            account_url: Blob-service endpoint, used with ``credential``.
            credential: Credential for ``account_url`` — an account key, a
                SAS token or a ``TokenCredential``; ``None`` for anonymous
                access to a public container.
            client: A ready ``BlobServiceClient``-like client (tests).
            signer: An ``_Signer`` for HMAC payload signing.  Required unless
                ``allow_unsigned=True`` is set.
            allow_unsigned: If ``True``, the store operates without signing.
                Requires ``PIRN_ALLOW_UNSIGNED=1`` in the environment.

        Raises:
            ValueError: If signing is not configured correctly.  A missing
                ``connection_string``/``account_url`` (with no ``client``) is
                reported on first use, not at construction.
        """
        super().__init__(signer=signer, allow_unsigned=allow_unsigned, prefix=prefix)
        self._container = container
        self._connection_string = connection_string
        self._account_url = account_url
        self._credential = credential
        self._client = client

    def _build_object_store(self) -> ObjectStore:
        from pirn.connectors.object_storage.azure_blob_config import AzureBlobConfig
        from pirn.connectors.object_storage.azure_blob_store import AzureBlobStore

        if self._client is None and self._connection_string is None and self._account_url is None:
            raise ValueError("AzureBlobDataStore requires either connection_string or account_url")
        config = AzureBlobConfig(
            container=self._container,
            connection_string=self._connection_string,
            account_url=self._account_url,
        )
        return AzureBlobStore(config, client=self._client, credential=self._credential)
