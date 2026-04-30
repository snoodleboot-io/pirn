"""Google Cloud Storage ``DataStore``.

Values are cloudpickled and stored as GCS objects keyed by content hash.
Suitable for GCP-hosted deployments.

Requires the ``gcloud-aio-storage`` package::

    pip install pirn[gcs]

Construction accepts an optional pre-built ``aiohttp.ClientSession`` for
testing.  In production the session is created lazily on first use.
"""

from __future__ import annotations

from typing import Any

from pirn.backends._signer import _Signer
from pirn.backends.base._cloud_object_store import _CloudObjectStore


class GCSDataStore(_CloudObjectStore):
    """``DataStore`` backed by a GCS bucket via gcloud-aio-storage.

    Each value is one GCS object at ``gs://{bucket}/{prefix}{hash}``.
    Use GCS object lifecycle rules for time-based scrubbing in production;
    ``scrub()`` deletes immediately for explicit removal.
    """

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "pirn/data/",
        service_file: str | None = None,
        session: Any = None,
        signer: _Signer | None = None,
    ) -> None:
        super().__init__(signer=signer)
        self._bucket = bucket
        self._prefix = prefix
        self._service_file = service_file
        self._session = session

    def _object_key(self, content_hash: str) -> str:
        clean = content_hash.removeprefix("sha256:")
        return f"{self._prefix}{clean}"

    def __storage(self) -> Any:
        try:
            from gcloud.aio.storage import Storage
        except ImportError as exc:
            raise ImportError(
                "GCSDataStore requires gcloud-aio-storage; install via `pip install pirn[gcs]`"
            ) from exc
        kwargs: dict[str, Any] = {}
        if self._service_file is not None:
            kwargs["service_file"] = self._service_file
        if self._session is not None:
            kwargs["session"] = self._session
        return Storage(**kwargs)

    async def _put_bytes(self, key: str, payload: bytes) -> None:
        async with self.__storage() as storage:
            await storage.upload(self._bucket, key, payload)

    async def _get_bytes(self, key: str) -> bytes:
        async with self.__storage() as storage:
            try:
                return await storage.download(self._bucket, key)
            except Exception as exc:
                if "404" in str(exc) or "Not Found" in str(exc):
                    raise KeyError(key) from exc
                raise

    async def _has_key(self, key: str) -> bool:
        async with self.__storage() as storage:
            try:
                await storage.download_metadata(self._bucket, key)
                return True
            except Exception:
                return False

    async def _delete_key(self, key: str) -> None:
        async with self.__storage() as storage:
            await storage.delete(self._bucket, key)
