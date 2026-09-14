"""S3 ``DataStore``.

Values are cloudpickled and stored as S3 objects keyed by content hash.
Suitable for distributed deployments where multiple workers need to read
and write intermediate values, and where TTL'd lifecycle policies manage
scrubbing.

MinIO: MinIO is S3-compatible.  Pass ``endpoint_url="http://minio:9000"``
to use this class against a MinIO cluster — no separate implementation
is needed.

Construction takes either an existing aioboto3 session (for tests) or
the bucket name (and optionally a key prefix and region).  The store
composes over :class:`~pirn.connectors.object_storage.s3_store.S3Store`,
which opens one S3 client on first use and holds it until
:meth:`~pirn.backends.base.data_store.DataStore.close` (PIR-869).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.backends.base.cloud_object_store import CloudObjectStore
from pirn.backends.signer import Signer

if TYPE_CHECKING:
    from pirn.connectors.object_store import ObjectStore


class S3DataStore(CloudObjectStore):
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
        signer: Signer | None = None,
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
            signer: An ``Signer`` for HMAC payload signing.  Required unless
                ``allow_unsigned=True`` is set.
            allow_unsigned: If ``True``, the store operates without signing.
                Requires ``PIRN_ALLOW_UNSIGNED=1`` in the environment.

        Raises:
            ValueError: If signing is not configured correctly.
        """
        super().__init__(signer=signer, allow_unsigned=allow_unsigned, prefix=prefix)
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url
        self._session = session

    def _build_object_store(self) -> ObjectStore:
        from pirn.connectors.object_storage.s3_config import S3Config
        from pirn.connectors.object_storage.s3_store import S3Store

        config = S3Config(
            bucket=self._bucket,
            region=self._region,
            endpoint_url=self._endpoint_url,
        )
        return S3Store(config, session=self._session)
