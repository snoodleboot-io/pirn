# pyright: reportUnnecessaryIsInstance=false
# runtime-bound inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""Azure Blob :class:`ObjectStore` backed by :mod:`azure-storage-blob` aio."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from pirn.connectors.object_storage.azure_blob_config import (
    AzureBlobConfig,
)
from pirn.connectors.object_store import ObjectStore
from pirn.core.optional_dependency import OptionalDependency


class AzureBlobStore(ObjectStore):
    """Async object store against Azure Blob Storage.

    Tests inject ``client=`` exposing the slice of the aio
    ``BlobServiceClient`` surface the store touches; production code
    constructs a real ``azure.storage.blob.aio.BlobServiceClient`` lazily
    and holds it until :meth:`close`. ``credential`` is an optional
    credential object (a ``TokenCredential``, a SAS token, ...) used with
    ``config.account_url`` in place of ``config.account_key``.
    """

    def __init__(
        self,
        config: AzureBlobConfig,
        *,
        client: Any | None = None,
        credential: Any | None = None,
    ) -> None:
        if not config.container:
            raise ValueError("AzureBlobConfig.container is required")
        if (
            client is None
            and not config.connection_string
            and not config.account_url
            and not (config.account_name and config.account_key)
        ):
            raise ValueError(
                "AzureBlobConfig requires either connection_string or account_url, "
                "or account_name and account_key"
            )
        self._config = config
        self._client: Any | None = client
        self._credential: Any | None = credential
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

        # design-decision-override: async-generator closure returned lazily; captures locals computed before iteration starts
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
        blob_client = client.get_blob_client(container=self._config.container, blob=key)
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
        blob_client = client.get_blob_client(container=self._config.container, blob=key)
        await blob_client.delete_blob()
        self._logger.debug(
            "azure.delete",
            extra={"container": self._config.container, "key": key},
        )

    async def exists(self, key: str) -> bool:
        """``BlobClient.exists`` presence check — no body download."""
        self._validate_key(key)
        client = await self._ensure_client()
        blob_client = client.get_blob_client(container=self._config.container, blob=key)
        return bool(await blob_client.exists())

    def is_not_found(self, exc: BaseException) -> bool:
        return "BlobNotFound" in type(exc).__name__ or "404" in str(exc)

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        client = await self._ensure_client()
        container_client = client.get_container_client(container=self._config.container)

        # design-decision-override: async-generator closure returned lazily; captures locals computed before iteration starts
        async def _iter() -> AsyncIterator[str]:
            kwargs: dict[str, Any] = {}
            if prefix:
                kwargs["name_starts_with"] = prefix
            async for blob in container_client.list_blobs(**kwargs):
                entry: Any = blob
                name: str | None = (
                    entry.get("name") if isinstance(blob, dict) else getattr(blob, "name", None)
                )
                if name is not None:
                    yield name

        return _iter()

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        blob_aio = OptionalDependency.require("azure.storage.blob.aio", extra="azure")
        if self._config.connection_string:
            self._owned_client = blob_aio.BlobServiceClient.from_connection_string(
                self._config.connection_string
            )
        else:
            account_url = (
                self._config.account_url
                or f"https://{self._config.account_name}.blob.core.windows.net"
            )
            credential = (
                self._credential if self._credential is not None else self._config.account_key
            )
            self._owned_client = blob_aio.BlobServiceClient(
                account_url=account_url,
                credential=credential,
            )
        self._client = self._owned_client
        return self._client
