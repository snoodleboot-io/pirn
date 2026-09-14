"""Google Cloud Storage :class:`ObjectStore` backed by :mod:`gcloud-aio-storage`."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from pirn.connectors.object_storage.gcs_config import GCSConfig
from pirn.connectors.object_store import ObjectStore
from pirn.core.optional_dependency import OptionalDependency


class GCSStore(ObjectStore):
    """Async object store against Google Cloud Storage.

    Tests inject ``client=`` exposing the slice of the gcloud-aio-storage
    surface the store touches (``download_stream`` / ``upload`` /
    ``delete`` / ``download_metadata`` / ``list_objects``); production code
    constructs a real ``gcloud.aio.storage.Storage`` client lazily (over
    ``session``, an ``aiohttp.ClientSession``, when one is supplied) and
    holds it until :meth:`close`.
    """

    def __init__(
        self,
        config: GCSConfig,
        *,
        client: Any | None = None,
        session: Any | None = None,
    ) -> None:
        if not config.bucket:
            raise ValueError("GCSConfig.bucket is required")
        self._config = config
        self._client: Any | None = client
        self._session: Any | None = session
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

        # design-decision-override: async-generator closure returned lazily; captures locals computed before iteration starts
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
                        f"GCSStore.put: body iterator must yield bytes; got {type(c).__name__}"
                    )
                chunks.append(bytes(c))
            payload = b"".join(chunks)
        await client.upload(bucket=self._config.bucket, object_name=key, file_data=payload)
        self._logger.debug(
            "gcs.put",
            extra={"bucket": self._config.bucket, "key": key, "size": len(payload)},
        )

    async def delete(self, key: str) -> None:
        self._validate_key(key)
        client = await self._ensure_client()
        await client.delete(bucket=self._config.bucket, object_name=key)
        self._logger.debug("gcs.delete", extra={"bucket": self._config.bucket, "key": key})

    async def exists(self, key: str) -> bool:
        """``download_metadata`` presence check; ``False`` only on a 404."""
        self._validate_key(key)
        client = await self._ensure_client()
        try:
            await client.download_metadata(self._config.bucket, key)
        except Exception as exc:
            if self.is_not_found(exc):
                return False
            raise
        return True

    def is_not_found(self, exc: BaseException) -> bool:
        text = str(exc)
        return "404" in text or "Not Found" in text

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        client = await self._ensure_client()
        bucket = self._config.bucket

        # design-decision-override: async-generator closure returned lazily; captures locals computed before iteration starts
        async def _iter() -> AsyncIterator[str]:
            page_token: str | None = None
            while True:
                params: dict[str, Any] = {"prefix": prefix} if prefix else {}
                if page_token is not None:
                    params["pageToken"] = page_token
                response = await client.list_objects(bucket=bucket, params=params)
                items: list[Any] = response.get("items") or []
                for item in items:
                    entry: Any = item
                    name: str | None = entry.get("name") if isinstance(item, dict) else item
                    if name is not None:
                        yield name
                page_token = response.get("nextPageToken")
                if not page_token:
                    return

        return _iter()

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        storage = OptionalDependency.require("gcloud.aio.storage", extra="gcs")
        kwargs: dict[str, Any] = {"service_file": self._config.service_account_json}
        if self._session is not None:
            kwargs["session"] = self._session
        self._owned_client = storage.Storage(**kwargs)
        self._client = self._owned_client
        return self._client
