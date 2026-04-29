"""S3 ``DataStore``.

Values are pickled and stored as S3 objects keyed by content hash.
Suitable for distributed deployments where multiple workers need to
read and write intermediate values, and where TTL'd lifecycle policies
manage scrubbing.

Construction takes either an existing aioboto3 session (for tests) or
the bucket name (and optionally a key prefix and region).  The session
is built lazily on first use.
"""

from __future__ import annotations

import pickle
from typing import Any


class S3DataStore:
    """``DataStore`` backed by an S3 bucket via aioboto3.

    Each value is one S3 object at ``s3://{bucket}/{prefix}{hash}``.
    Use S3 lifecycle rules for time-based scrubbing in production;
    ``scrub()`` deletes immediately for explicit removal.
    """

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "pirn/data/",
        region: str | None = None,
        endpoint_url: str | None = None,
        session: Any = None,
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix
        self._region = region
        self._endpoint_url = endpoint_url
        self._session = session

    def _key(self, content_hash: str) -> str:
        clean = content_hash.removeprefix("sha256:")
        return f"{self._prefix}{clean}"

    async def _client(self) -> Any:
        """Return an async S3 client, creating a session if needed.

        Uses ``aioboto3.Session.client`` as a context manager — callers
        wrap each operation in ``async with`` so the client is properly
        closed.
        """
        if self._session is None:
            try:
                import aioboto3
            except ImportError as exc:
                raise ImportError(
                    "S3DataStore requires aioboto3; install via "
                    "`pip install pirn[s3]`"
                ) from exc
            self._session = aioboto3.Session()
        return self._session

    async def put(self, content_hash: str, value: Any) -> None:
        session = await self._client()
        payload = pickle.dumps(value)
        async with session.client("s3", region_name=self._region, endpoint_url=self._endpoint_url) as s3:
            await s3.put_object(
                Bucket=self._bucket,
                Key=self._key(content_hash),
                Body=payload,
            )

    async def get(self, content_hash: str) -> Any:
        session = await self._client()
        async with session.client("s3", region_name=self._region, endpoint_url=self._endpoint_url) as s3:
            try:
                response = await s3.get_object(
                    Bucket=self._bucket,
                    Key=self._key(content_hash),
                )
            except Exception as exc:
                # Translate any backend NoSuchKey-style error to KeyError
                # so DataStore consumers can use uniform error handling.
                err_name = type(exc).__name__
                if "NoSuchKey" in err_name or "404" in str(exc):
                    raise KeyError(content_hash) from exc
                raise
            payload = await response["Body"].read()
        return pickle.loads(payload)

    async def has(self, content_hash: str) -> bool:
        session = await self._client()
        async with session.client("s3", region_name=self._region, endpoint_url=self._endpoint_url) as s3:
            try:
                await s3.head_object(
                    Bucket=self._bucket,
                    Key=self._key(content_hash),
                )
                return True
            except Exception:
                return False

    async def scrub(self, content_hash: str) -> None:
        session = await self._client()
        async with session.client("s3", region_name=self._region, endpoint_url=self._endpoint_url) as s3:
            await s3.delete_object(
                Bucket=self._bucket,
                Key=self._key(content_hash),
            )
