"""S3-compatible :class:`ObjectStore` backed by :mod:`aioboto3`."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from pirn.connectors.object_storage.s3_config import S3Config
from pirn.connectors.object_store import ObjectStore


class S3Store(ObjectStore):
    """Async object store against AWS S3 / MinIO / Cloudflare R2 / GCS via S3 API.

    Tests inject ``client=`` exposing the slice of the boto3 S3 client we
    touch (``get_object`` / ``put_object`` / ``delete_object`` /
    ``list_objects_v2``); production code constructs a real aioboto3 client
    lazily.
    """

    def __init__(
        self,
        config: S3Config,
        *,
        client: Any | None = None,
    ) -> None:
        if not config.bucket:
            raise ValueError("S3Config.bucket is required")
        self._config = config
        self._client = client
        self._owned_session: Any = None
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> S3Config:
        return self._config

    async def close(self) -> None:
        if self._owned_session is not None:
            await self._owned_session.__aexit__(None, None, None)
            self._owned_session = None
            self._client = None

    async def get(self, key: str) -> AsyncIterator[bytes]:
        self._validate_key(key)
        client = await self._ensure_client()
        chunk_size = self._config.chunk_size
        bucket = self._config.bucket

        async def _iter() -> AsyncIterator[bytes]:
            response = await client.get_object(Bucket=bucket, Key=key)
            body = response["Body"]
            try:
                while True:
                    chunk = await body.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                close_method = getattr(body, "close", None)
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
                        f"S3Store.put: body iterator must yield bytes; got {type(c).__name__}"
                    )
                chunks.append(bytes(c))
            payload = b"".join(chunks)
        await client.put_object(Bucket=self._config.bucket, Key=key, Body=payload)
        self._logger.debug(
            "s3.put", extra={"bucket": self._config.bucket, "key": key, "size": len(payload)}
        )

    async def delete(self, key: str) -> None:
        self._validate_key(key)
        client = await self._ensure_client()
        await client.delete_object(Bucket=self._config.bucket, Key=key)
        self._logger.debug("s3.delete", extra={"bucket": self._config.bucket, "key": key})

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        client = await self._ensure_client()
        bucket = self._config.bucket

        async def _iter() -> AsyncIterator[str]:
            continuation: str | None = None
            while True:
                kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
                if continuation is not None:
                    kwargs["ContinuationToken"] = continuation
                response = await client.list_objects_v2(**kwargs)
                for item in response.get("Contents", []) or []:
                    yield item["Key"]
                if not response.get("IsTruncated"):
                    return
                continuation = response.get("NextContinuationToken")

        return _iter()

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import aioboto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "S3Store requires aioboto3; install via `pip install pirn[s3]`"
            ) from exc
        session = aioboto3.Session()
        self._owned_session = session.client(
            "s3",
            region_name=self._config.region,
            endpoint_url=self._config.endpoint_url,
            aws_access_key_id=self._config.access_key_id,
            aws_secret_access_key=self._config.secret_access_key,
            aws_session_token=self._config.session_token,
        )
        self._client = await self._owned_session.__aenter__()
        return self._client
