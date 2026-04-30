"""Azure Blob Storage ``DataStore``.

Values are cloudpickled and stored as Azure Blob objects keyed by
content hash.  Suitable for Azure-hosted deployments.

Requires the ``azure-storage-blob`` package::

    pip install pirn[azure]

Construction accepts a connection string or an account URL with a
credential.  An optional pre-built ``BlobServiceClient`` can be passed
directly for testing.
"""

from __future__ import annotations

from typing import Any

from pirn.backends._signer import _Signer
from pirn.backends.base._cloud_object_store import _CloudObjectStore


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
    ) -> None:
        super().__init__(signer=signer)
        self._container = container
        self._prefix = prefix
        self._connection_string = connection_string
        self._account_url = account_url
        self._credential = credential
        self._client = client

    def _object_key(self, content_hash: str) -> str:
        clean = content_hash.removeprefix("sha256:")
        return f"{self._prefix}{clean}"

    def __service_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from azure.storage.blob.aio import BlobServiceClient
        except ImportError as exc:
            raise ImportError(
                "AzureBlobDataStore requires azure-storage-blob; "
                "install via `pip install pirn[azure]`"
            ) from exc
        if self._connection_string is not None:
            return BlobServiceClient.from_connection_string(self._connection_string)
        if self._account_url is not None:
            return BlobServiceClient(self._account_url, credential=self._credential)
        raise ValueError("AzureBlobDataStore requires either connection_string or account_url")

    async def _put_bytes(self, key: str, payload: bytes) -> None:
        async with self.__service_client() as svc:
            blob = svc.get_blob_client(container=self._container, blob=key)
            await blob.upload_blob(payload, overwrite=True)

    async def _get_bytes(self, key: str) -> bytes:
        async with self.__service_client() as svc:
            blob = svc.get_blob_client(container=self._container, blob=key)
            try:
                stream = await blob.download_blob()
                return await stream.readall()
            except Exception as exc:
                if "BlobNotFound" in type(exc).__name__ or "404" in str(exc):
                    raise KeyError(key) from exc
                raise

    async def _has_key(self, key: str) -> bool:
        async with self.__service_client() as svc:
            blob = svc.get_blob_client(container=self._container, blob=key)
            return await blob.exists()

    async def _delete_key(self, key: str) -> None:
        async with self.__service_client() as svc:
            blob = svc.get_blob_client(container=self._container, blob=key)
            await blob.delete_blob(delete_snapshots="include")
