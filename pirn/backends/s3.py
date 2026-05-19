"""S3 ``DataStore``.

Values are cloudpickled and stored as S3 objects keyed by content hash.
Suitable for distributed deployments where multiple workers need to read
and write intermediate values, and where TTL'd lifecycle policies manage
scrubbing.

MinIO: MinIO is S3-compatible.  Pass ``endpoint_url="http://minio:9000"``
to use this class against a MinIO cluster — no separate implementation
is needed.

Construction takes either an existing aioboto3 session (for tests) or
the bucket name (and optionally a key prefix and region).  The session
is built lazily on first use.
"""

from __future__ import annotations

from typing import Any

from pirn.backends._signer import _Signer
from pirn.backends.base._cloud_object_store import _CloudObjectStore


class S3DataStore(_CloudObjectStore):
    """``DataStore`` backed by an S3 bucket via aioboto3.

    Each value is one S3 object at ``s3://{bucket}/{prefix}{hash}``.
    Use S3 lifecycle rules for time-based scrubbing in production;
    ``scrub()`` deletes immediately for explicit removal.

    Works with any S3-compatible store (MinIO, Ceph, Cloudflare R2) by
    passing the appropriate ``endpoint_url``.
    """

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "pirn/data/",
        region: str | None = None,
        endpoint_url: str | None = None,
        session: Any = None,
        signer: _Signer | None = None,
        allow_unsigned: bool = False,
    ) -> None:
        """Initialise the store.

        Args:
            bucket: Name of the S3 bucket to use.
            prefix: Key prefix for all objects written by this store.
                Defaults to ``"pirn/data/"`` to avoid collision with other
                objects in the bucket.
            region: AWS region for the bucket.  ``None`` uses the default
                region configured in the environment.
            endpoint_url: Custom endpoint URL for S3-compatible stores such
                as MinIO, Ceph, or Cloudflare R2.
            session: An existing ``aioboto3.Session`` to reuse.  If ``None``
                a new session is created lazily on first use.
            signer: An ``_Signer`` for HMAC payload signing.  Required unless
                ``allow_unsigned=True`` is set.
            allow_unsigned: If ``True``, the store operates without signing.
                Requires ``PIRN_ALLOW_UNSIGNED=1`` in the environment.

        Raises:
            ValueError: If signing is not configured correctly.
        """
        super().__init__(signer=signer, allow_unsigned=allow_unsigned)
        self._bucket = bucket
        self._prefix = prefix
        self._region = region
        self._endpoint_url = endpoint_url
        self._session = session

    def _object_key(self, content_hash: str) -> str:
        """Derive the S3 object key from a content hash.

        Args:
            content_hash: SHA-256 hex digest, possibly prefixed with
                ``sha256:``.

        Returns:
            S3 object key of the form ``{prefix}{hash}``.
        """
        clean = content_hash.removeprefix("sha256:")
        return f"{self._prefix}{clean}"

    async def __client(self) -> Any:
        if self._session is None:
            try:
                import aioboto3
            except ImportError as exc:
                raise ImportError(
                    "S3DataStore requires aioboto3; install via `pip install pirn[s3]`"
                ) from exc
            self._session = aioboto3.Session()
        return self._session

    def __s3(self, session: Any) -> Any:
        return session.client("s3", region_name=self._region, endpoint_url=self._endpoint_url)

    async def _put_bytes(self, key: str, payload: bytes) -> None:
        """Upload raw bytes as an S3 object.

        Args:
            key: S3 object key returned by :meth:`_object_key`.
            payload: Bytes to upload.
        """
        session = await self.__client()
        async with self.__s3(session) as s3:
            await s3.put_object(Bucket=self._bucket, Key=key, Body=payload)

    async def _get_bytes(self, key: str) -> bytes:
        """Download raw bytes from an S3 object.

        Args:
            key: S3 object key returned by :meth:`_object_key`.

        Returns:
            Object body as bytes.

        Raises:
            KeyError: If the object does not exist (NoSuchKey / 404).
        """
        session = await self.__client()
        async with self.__s3(session) as s3:
            try:
                response = await s3.get_object(Bucket=self._bucket, Key=key)
            except Exception as exc:
                err_name = type(exc).__name__
                if "NoSuchKey" in err_name or "404" in str(exc):
                    raise KeyError(key) from exc
                raise
            return await response["Body"].read()

    async def _has_key(self, key: str) -> bool:
        """Return ``True`` if an S3 object exists at ``key``.

        Uses ``head_object`` to avoid downloading the object body.

        Args:
            key: S3 object key returned by :meth:`_object_key`.

        Returns:
            ``True`` if the object exists, ``False`` on 404/NoSuchKey.

        Raises:
            Exception: Any S3 error other than not-found is re-raised.
        """
        session = await self.__client()
        async with self.__s3(session) as s3:
            try:
                await s3.head_object(Bucket=self._bucket, Key=key)
                return True
            except Exception as exc:
                err_name = type(exc).__name__
                err_str = str(exc)
                if (
                    "NoSuchKey" in err_name
                    or "NoSuchKey" in err_str
                    or "404" in err_str
                    or "NotFound" in err_name
                ):
                    return False
                raise

    async def _delete_key(self, key: str) -> None:
        """Delete an S3 object.

        S3 ``delete_object`` is idempotent — deleting a non-existent object
        succeeds silently.

        Args:
            key: S3 object key returned by :meth:`_object_key`.
        """
        session = await self.__client()
        async with self.__s3(session) as s3:
            await s3.delete_object(Bucket=self._bucket, Key=key)
