"""``S3BlobStore`` — an S3-compatible object storage backend (F16-S4 / PIR-363).

Implements :class:`~pirn_agents.connectors.blob_store.BlobStore` against any
S3-compatible endpoint via ``aioboto3`` (the ``[s3]`` extra), lazily imported so
importing this module stays backend-free. The pooled client is built once and
reused for the whole run (the pooling lever, AD-3) and torn down by :meth:`close`.

Streaming is genuine on both directions:

* :meth:`get` yields the response body via ``iter_chunks`` — the object is never
  fully read into memory;
* :meth:`put` performs a **multipart** upload, buffering at most one ``part_size``
  window before flushing each part, so an arbitrarily large object streams up
  without being resident.

An injected ``client`` keeps unit tests fully offline.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from pirn_agents._require import _require
from pirn_agents.connectors.blob_store import BlobStore
from pirn_agents.credential_ref import CredentialRef


class S3BlobStore(BlobStore):
    """S3-compatible :class:`BlobStore` with streaming get and multipart put."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        region: str | None = None,
        credential: CredentialRef | None = None,
        chunk_size: int = 65536,
        part_size: int = 5 * 1024 * 1024,
        client: Any | None = None,
    ) -> None:
        """Configure the bucket, endpoint, and streaming windows.

        Args:
            bucket: Target S3 bucket name.
            endpoint_url: Optional custom endpoint (S3-compatible services).
            region: Optional AWS region name.
            credential: Optional :class:`CredentialRef` (unused by the injected
                client path; reserved for the real ``aioboto3`` session).
            chunk_size: Download streaming chunk size (bytes).
            part_size: Multipart upload part size (bytes); each part buffers at
                most this many bytes before it is flushed.
            client: Optional pre-built S3-client double pooled as-is (tests).

        Raises:
            TypeError: If ``credential`` is not a ``CredentialRef`` or ``None``.
            ValueError: If ``bucket`` is empty or a streaming window is not positive.
        """
        if credential is not None and not isinstance(credential, CredentialRef):
            raise TypeError(
                f"S3BlobStore: credential must be a CredentialRef or None, "
                f"got {type(credential).__name__}"
            )
        if not bucket:
            raise ValueError("S3BlobStore: bucket must be a non-empty name")
        if chunk_size <= 0 or part_size <= 0:
            raise ValueError("S3BlobStore: chunk_size and part_size must be positive")
        self._bucket = bucket
        self._endpoint_url = endpoint_url
        self._region = region
        self._credential = credential
        self._chunk_size = chunk_size
        self._part_size = part_size
        self._client: Any | None = client
        self._client_cm: Any | None = None

    async def _get_client(self) -> Any:
        """Return the pooled S3 client, building and entering it once."""
        if self._client is None:
            aioboto3 = _require("s3", "aioboto3")
            session = aioboto3.Session()
            client_cm: Any = session.client(
                "s3", endpoint_url=self._endpoint_url, region_name=self._region
            )
            self._client_cm = client_cm
            self._client = await client_cm.__aenter__()
        return self._client

    async def get(self, key: str) -> AsyncIterator[bytes]:
        """Stream the object at ``key`` chunk-by-chunk via ``get_object``."""
        client = await self._get_client()
        response = await client.get_object(Bucket=self._bucket, Key=key)
        body = response["Body"]
        async for chunk in body.iter_chunks(self._chunk_size):
            yield chunk

    async def put(self, key: str, data: AsyncIterator[bytes]) -> None:
        """Multipart-upload ``data`` into ``key``, flushing one part at a time."""
        client = await self._get_client()
        created = await client.create_multipart_upload(Bucket=self._bucket, Key=key)
        upload_id = created["UploadId"]
        parts: list[dict[str, Any]] = []
        buffer = bytearray()
        part_number = 1
        try:
            async for chunk in data:
                buffer.extend(chunk)
                while len(buffer) >= self._part_size:
                    part = bytes(buffer[: self._part_size])
                    del buffer[: self._part_size]
                    parts.append(await self._upload_part(client, key, upload_id, part_number, part))
                    part_number += 1
            if buffer or not parts:
                parts.append(
                    await self._upload_part(client, key, upload_id, part_number, bytes(buffer))
                )
            await client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except BaseException:
            await client.abort_multipart_upload(Bucket=self._bucket, Key=key, UploadId=upload_id)
            raise

    async def _upload_part(
        self, client: Any, key: str, upload_id: str, part_number: int, body: bytes
    ) -> dict[str, Any]:
        """Upload one multipart part and return its ``{ETag, PartNumber}`` record."""
        response = await client.upload_part(
            Bucket=self._bucket,
            Key=key,
            UploadId=upload_id,
            PartNumber=part_number,
            Body=body,
        )
        return {"ETag": response["ETag"], "PartNumber": part_number}

    async def list(self, prefix: str = "") -> Sequence[str]:
        """Return every object key under ``prefix``, following pagination."""
        client = await self._get_client()
        keys: list[str] = []
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": self._bucket, "Prefix": prefix}
            if token is not None:
                kwargs["ContinuationToken"] = token
            response = await client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                keys.append(obj["Key"])
            if response.get("IsTruncated"):
                token = response.get("NextContinuationToken")
            else:
                break
        return keys

    async def close(self) -> None:
        """Exit the pooled client's async context and scrub the credential."""
        if self._client_cm is not None:
            await self._client_cm.__aexit__(None, None, None)
            self._client_cm = None
        self._client = None
        self._credential = None
