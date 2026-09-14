"""Google Cloud Storage ``DataStore``.

Values are cloudpickled and stored as GCS objects keyed by content hash.
Suitable for GCP-hosted deployments.

Requires the ``gcloud-aio-storage`` package::

    pip install "pirn-core[gcs]"

Construction accepts an optional pre-built ``aiohttp.ClientSession``
(``session=``) or a ready ``gcloud.aio.storage.Storage``-like client
(``client=``, for tests).  The store composes over
:class:`~pirn.connectors.object_storage.gcs_store.GCSStore`, which opens
one storage client on first use and holds it until
:meth:`~pirn.backends.base.data_store.DataStore.close` (PIR-869).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.backends.base._cloud_object_store import _CloudObjectStore
from pirn.backends.signer import Signer

if TYPE_CHECKING:
    from pirn.connectors.object_store import ObjectStore


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
        client: Any = None,
        signer: Signer | None = None,
        allow_unsigned: bool = False,
    ) -> None:
        """Initialise the store.

        Args:
            bucket: Name of the GCS bucket to use.
            prefix: Key prefix for all objects written by this store.
            service_file: Path to a service-account JSON key file.  ``None``
                falls back to Application Default Credentials.
            session: An existing ``aiohttp.ClientSession`` for the storage
                client to reuse.
            client: A ready ``gcloud.aio.storage.Storage``-like client
                (tests).  When given, ``service_file``/``session`` are unused.
            signer: An ``Signer`` for HMAC payload signing.  Required unless
                ``allow_unsigned=True`` is set.
            allow_unsigned: If ``True``, the store operates without signing.
                Requires ``PIRN_ALLOW_UNSIGNED=1`` in the environment.

        Raises:
            ValueError: If signing is not configured correctly.
        """
        super().__init__(signer=signer, allow_unsigned=allow_unsigned, prefix=prefix)
        self._bucket = bucket
        self._service_file = service_file
        self._session = session
        self._client = client

    def _build_object_store(self) -> ObjectStore:
        from pirn.connectors.object_storage.gcs_config import GCSConfig
        from pirn.connectors.object_storage.gcs_store import GCSStore

        config = GCSConfig(bucket=self._bucket, service_account_json=self._service_file)
        return GCSStore(config, client=self._client, session=self._session)
