"""Google Cloud Storage :class:`ObjectStore` backed by :mod:`gcloud-aio-storage`."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from pirn.domains.connectors.object_storage.gcs_config import GCSConfig
from pirn.domains.connectors.object_store import ObjectStore


class GCSStore(ObjectStore):
    """Async object store against Google Cloud Storage.

    Tests inject ``client=`` exposing the slice of the gcloud-aio-storage
    surface the store touches (``download_stream`` / ``upload`` /
    ``delete`` / ``list_objects``); production code constructs a real
    ``gcloud.aio.storage.Storage`` client lazily.
    """

    def __init__(
        self,
        config: GCSConfig,
        *,
        client: Any | None = None,
    ) -> None:
        if not config.bucket:
            raise ValueError("GCSConfig.bucket is required")
        self._config = config
        self._client = client
        self._owned_client: Any = None
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> GCSConfig:
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
        bucket = self._config.bucket

        async def _iter() -> AsyncIterator[bytes]:
            stream = await client.download_stream(bucket=bucket, object_name=key)
            try:
                while True:
                    chunk = await stream.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                close_method = getattr(stream, "close", None)
                if close_method is not None:
                    result = close_method()
                    if hasattr(result, "__await__"):
                        await result

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
                        "GCSStore.put: body iterator must yield bytes; "
                        f"got {type(c).__name__}"
                    )
                chunks.append(bytes(c))
            payload = b"".join(chunks)
        await client.upload(
            bucket=self._config.bucket, object_name=key, file_data=payload
        )
        self._logger.debug(
            "gcs.put",
            extra={"bucket": self._config.bucket, "key": key, "size": len(payload)},
        )

    async def delete(self, key: str) -> None:
        self._validate_key(key)
        client = await self._ensure_client()
        await client.delete(bucket=self._config.bucket, object_name=key)
        self._logger.debug(
            "gcs.delete", extra={"bucket": self._config.bucket, "key": key}
        )

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        client = await self._ensure_client()
        bucket = self._config.bucket

        async def _iter() -> AsyncIterator[str]:
            page_token: str | None = None
            while True:
                params: dict[str, Any] = {"prefix": prefix} if prefix else {}
                if page_token is not None:
                    params["pageToken"] = page_token
                response = await client.list_objects(bucket=bucket, params=params)
                for item in response.get("items", []) or []:
                    name = item.get("name") if isinstance(item, dict) else item
                    if name is not None:
                        yield name
                page_token = response.get("nextPageToken")
                if not page_token:
                    return

        return _iter()

    def _validate_key(self, key: str) -> None:
        if not key:
            raise ValueError("key must be non-empty")
        if "\x00" in key:
            raise ValueError("key contains NUL byte")
        if key.startswith("/"):
            raise ValueError("key must not start with '/'")
        parts = key.split("/")
        if any(p == ".." for p in parts):
            raise ValueError("key must not contain '..' segments")

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from gcloud.aio.storage import Storage  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "GCSStore requires gcloud-aio-storage; "
                "install via `pip install pirn[gcs]`"
            ) from exc
        self._owned_client = Storage(
            service_file=self._config.service_account_json,
        )
        self._client = self._owned_client
        return self._client
