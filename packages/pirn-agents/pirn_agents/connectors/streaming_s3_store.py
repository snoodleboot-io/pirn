"""``StreamingS3Store`` — core :class:`S3Store` with a genuinely streaming put.

The agents layer previously shipped its own `S3BlobStore` against a parallel
`BlobStore` interface, which silently dropped core's ``_validate_key``
path-traversal guard (PIR-690). This subclasses core's :class:`S3Store` instead,
so key validation, ``get``/``delete``/``list``, credential scrubbing, and client
lifecycle all come from core — the only thing added back is the one capability
core lacks.

Core's ``S3Store.put`` buffers the whole body into a single ``bytes`` before
calling ``put_object``, so an arbitrarily large upload is fully resident in
memory. ``S3Config`` already declares ``multipart_threshold`` and ``chunk_size``,
but nothing consumes them. This override performs a real **multipart** upload,
buffering at most one ``part_size`` window before flushing each part, and aborts
the upload if any part fails.

Requires the ``[s3]`` extra (``aioboto3``), lazily imported by core's client
builder so importing this module stays backend-free. An injected ``client``
keeps unit tests fully offline.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from pirn.connectors.object_storage.s3_config import S3Config
from pirn.connectors.object_storage.s3_store import S3Store


class StreamingS3Store(S3Store):
    """S3 object store whose ``put`` streams a multipart upload."""

    # S3 rejects a non-final part below this size at completion time.
    _MIN_PART_SIZE: int = 5 * 1024 * 1024

    def __init__(
        self,
        config: S3Config,
        *,
        client: Any | None = None,
        part_size: int | None = None,
    ) -> None:
        """Configure the store and its multipart window.

        Args:
            config: Core S3 connection config (bucket, region, endpoint, creds).
            client: Optional pre-built S3-client double, pooled as-is (tests).
            part_size: Multipart part size in bytes. Each part buffers at most
                this many bytes before being flushed. Defaults to the config's
                ``multipart_threshold``, which this store is the first consumer of.
                Must be at least 5 MiB — S3 rejects a smaller non-final part with
                ``EntityTooSmall``, and only at completion, after the whole body
                has been uploaded.

        Raises:
            ValueError: If ``config.bucket`` is empty or ``part_size`` is below
                S3's 5 MiB minimum.
        """
        super().__init__(config, client=client)
        resolved = part_size if part_size is not None else config.multipart_threshold
        if resolved < self._MIN_PART_SIZE:
            raise ValueError(
                f"StreamingS3Store: part_size must be at least {self._MIN_PART_SIZE} bytes "
                f"(S3's minimum for a non-final part), got {resolved!r}"
            )
        self._part_size = resolved

    @property
    def part_size(self) -> int:
        """Bytes buffered per multipart part before flushing."""
        return self._part_size

    async def put(self, key: str, body: AsyncIterator[bytes] | bytes) -> None:
        """Upload ``body`` to ``key``, streaming a multipart upload for iterators.

        A ``bytes`` body has nothing to stream, so it defers to core's single
        ``put_object``. An iterator is uploaded part by part so an arbitrarily
        large object never becomes resident.

        Args:
            key: Destination object key. Validated by core's ``_validate_key``.
            body: The object content, as ``bytes`` or an async iterator of chunks.

        Raises:
            ValueError: If ``key`` is rejected by core's path-traversal guard.
            TypeError: If the iterator yields a non-bytes chunk.
        """
        if isinstance(body, (bytes, bytearray)):
            await super().put(key, bytes(body))
            return
        self._validate_key(key)
        buffer = bytearray()
        client: Any = None
        # Empty until a full part exists and the multipart upload is opened.
        upload_id: str = ""
        parts: list[dict[str, Any]] = []
        part_number = 1
        try:
            async for chunk in body:
                if not isinstance(chunk, (bytes, bytearray)):
                    raise TypeError(
                        f"StreamingS3Store.put: body iterator must yield bytes; "
                        f"got {type(chunk).__name__}"
                    )
                buffer.extend(chunk)
                while len(buffer) >= self._part_size:
                    if not upload_id:
                        # Deferred: only start a multipart upload once a full part
                        # exists, so a small body never opens one it cannot satisfy.
                        client = await self._ensure_client()
                        created = await client.create_multipart_upload(
                            Bucket=self.config.bucket, Key=key
                        )
                        upload_id = str(created["UploadId"])
                    part = bytes(buffer[: self._part_size])
                    del buffer[: self._part_size]
                    parts.append(await self._upload_part(client, key, upload_id, part_number, part))
                    part_number += 1
            if not upload_id:
                # The body never reached one full part, so there is nothing to
                # multipart: a single PUT is correct, cheaper, and avoids the
                # 0-byte / sub-minimum part S3 would reject.
                await super().put(key, bytes(buffer))
                return
            if buffer:
                parts.append(
                    await self._upload_part(client, key, upload_id, part_number, bytes(buffer))
                )
            await client.complete_multipart_upload(
                Bucket=self.config.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            self._logger.debug(
                "s3.put.multipart",
                extra={"bucket": self.config.bucket, "key": key, "parts": len(parts)},
            )
        except BaseException:
            if upload_id:
                await self._abort_quietly(client, key, upload_id)
            raise

    async def _abort_quietly(self, client: Any, key: str, upload_id: str) -> None:
        """Abort the upload so S3 retains no orphaned parts, which continue to bill.

        Shielded and swallowing: this runs while an exception is already in flight,
        and the usual cause of a mid-upload failure — a dead connection — is exactly
        when abort also fails. Letting it raise would replace the real error.
        """
        try:
            await asyncio.shield(
                client.abort_multipart_upload(
                    Bucket=self.config.bucket, Key=key, UploadId=upload_id
                )
            )
        except BaseException:
            self._logger.warning(
                "s3.abort_multipart_failed",
                extra={"bucket": self.config.bucket, "key": key, "upload_id": upload_id},
            )

    async def _upload_part(
        self, client: Any, key: str, upload_id: str, part_number: int, body: bytes
    ) -> dict[str, Any]:
        response = await client.upload_part(
            Bucket=self.config.bucket,
            Key=key,
            PartNumber=part_number,
            UploadId=upload_id,
            Body=body,
        )
        return {"ETag": response["ETag"], "PartNumber": part_number}
