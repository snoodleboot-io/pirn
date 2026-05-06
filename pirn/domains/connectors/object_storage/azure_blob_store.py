"""Azure Blob :class:`ObjectStore` backed by :mod:`azure-storage-blob` aio."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from pirn.domains.connectors.object_storage.azure_blob_config import (
    AzureBlobConfig,
)
from pirn.domains.connectors.object_store import ObjectStore


class AzureBlobStore(ObjectStore):
    """Async object store against Azure Blob Storage.

    Tests inject ``client=`` exposing the slice of the aio
    ``BlobServiceClient`` surface the store touches; production code
    constructs a real ``azure.storage.blob.aio.BlobServiceClient`` lazily.
    """

    def __init__(
        self,
        config: AzureBlobConfig,
        *,
        client: Any | None = None,
    ) -> None:
        if not config.container:
            raise ValueError("AzureBlobConfig.container is required")
        if (
            client is None
            and not config.connection_string
            and not (config.account_name and config.account_key)
        ):
            raise ValueError(
                "AzureBlobConfig requires either connection_string or "
                "account_name and account_key"
            )
        self._config = config
        self._client = client
        self._owned_client: Any = None
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> AzureBlobConfig:
        return self._config

    async def close(self) -> None:
        if self._owned_client is not None:
            close_method = getattr(self._owned_client, "close", None)
            if close_method is not None:
                result = close_method()
                if hasattr(result, "__await__"):
                    await result
            self._owned_client = None
            self._client = None

    async def get(self, key: str) -> AsyncIterator[bytes]:
        self._validate_key(key)
        client = await self._ensure_client()
        chunk_size = self._config.chunk_size
        container = self._config.container
        blob_client = client.get_blob_client(container=container, blob=key)

        async def _iter() -> AsyncIterator[bytes]:
            downloader = await blob_client.download_blob()
            async for chunk in downloader.chunks(chunk_size):
                if chunk:
                    yield chunk

        return _iter()

    async def put(self, key: str, body: AsyncIterator[bytes] | bytes) -> None:
        self._validate_key(key)
        client = await self._ensure_client()
        if isinstance(body, (bytes, bytearray)):
            payload: bytes = bytes(body)
        else:
            chunks: list[bytes] = []
            async for c in body:
                if not isinstance(c, (bytes, bytearray)):
                    raise TypeError(
                        "AzureBlobStore.put: body iterator must yield bytes; "
                        f"got {type(c).__name__}"
                    )
                chunks.append(bytes(c))
            payload = b"".join(chunks)
        blob_client = client.get_blob_client(
            container=self._config.container, blob=key
        )
        await blob_client.upload_blob(payload, overwrite=True)
        self._logger.debug(
            "azure.put",
            extra={
                "container": self._config.container,
                "key": key,
                "size": len(payload),
            },
        )

    async def delete(self, key: str) -> None:
        self._validate_key(key)
        client = await self._ensure_client()
        blob_client = client.get_blob_client(
            container=self._config.container, blob=key
        )
        await blob_client.delete_blob()
        self._logger.debug(
            "azure.delete",
            extra={"container": self._config.container, "key": key},
        )

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        client = await self._ensure_client()
        container_client = client.get_container_client(
            container=self._config.container
        )

        async def _iter() -> AsyncIterator[str]:
            kwargs: dict[str, Any] = {}
            if prefix:
                kwargs["name_starts_with"] = prefix
            async for blob in container_client.list_blobs(**kwargs):
                name = (
                    blob.get("name")
                    if isinstance(blob, dict)
                    else getattr(blob, "name", None)
                )
                if name is not None:
                    yield name

        return _iter()


    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from azure.storage.blob.aio import (  # type: ignore[import-not-found]
                BlobServiceClient,
            )
        except ImportError as exc:
            raise ImportError(
                "AzureBlobStore requires azure-storage-blob; "
                "install via `pip install pirn[azure]`"
            ) from exc
        if self._config.connection_string:
            self._owned_client = BlobServiceClient.from_connection_string(
                self._config.connection_string
            )
        else:
            account_url = (
                f"https://{self._config.account_name}.blob.core.windows.net"
            )
            self._owned_client = BlobServiceClient(
                account_url=account_url,
                credential=self._config.account_key,
            )
        self._client = self._owned_client
        return self._client
