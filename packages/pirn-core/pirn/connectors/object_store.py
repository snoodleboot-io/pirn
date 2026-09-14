"""Interface for async object stores (S3, GCS, Azure Blob, local filesystem).

Reads stream as :class:`AsyncIterator[bytes]` so the connector never needs
to load a full object into memory.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.exceptions.connector_closed_error import ConnectorClosedError


class ObjectStore(PirnOpaqueValue):
    """Interface every connector object-store implementation must satisfy.

    Implementations:
      - :class:`pirn.connectors.object_storage.local_filesystem_store.LocalFilesystemStore`
      - :class:`pirn.connectors.object_storage.s3_store.S3Store`

    Pydantic treats stores as opaque (see
    :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
    identity-keyed serialiser keeps content-addressing cache stable
    without descending into engine internals (boto3, gcs, ...).
    """

    async def get(self, key: str) -> AsyncIterator[bytes]:
        """Stream the bytes of the object at ``key``."""
        raise NotImplementedError(f"{type(self).__name__} must implement get()")

    async def put(self, key: str, body: AsyncIterator[bytes] | bytes) -> None:
        """Write ``body`` to ``key`` — bytes or an async iterator of bytes."""
        raise NotImplementedError(f"{type(self).__name__} must implement put()")

    async def delete(self, key: str) -> None:
        """Remove the object at ``key``. Idempotent."""
        raise NotImplementedError(f"{type(self).__name__} must implement delete()")

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        """Yield all keys under ``prefix`` in lexicographic order."""
        raise NotImplementedError(f"{type(self).__name__} must implement list()")

    async def exists(self, key: str) -> bool:
        """Return ``True`` if an object is stored at ``key``.

        The default walks :meth:`list` under ``key`` and looks for an exact
        match, which is correct for every backend but costs a listing;
        concrete stores override it with the backend's metadata call
        (``head_object``, ``download_metadata``, ``BlobClient.exists``, a
        ``stat``) so a presence check never downloads the body. Introduced so
        a content-addressed ``DataStore`` can compose over an ``ObjectStore``
        (PIR-869) — ``DataStore.has()`` is exactly this question.
        """
        self._validate_key(key)
        async for candidate in await self.list(key):
            if candidate == key:
                return True
        return False

    def is_not_found(self, exc: BaseException) -> bool:
        """Classify a backend exception raised by :meth:`get` as "no such key".

        Backends surface a missing object as their SDK's own error type
        (botocore ``NoSuchKey``, a gcloud-aio 404, Azure ``BlobNotFound``);
        a caller that needs a uniform ``KeyError`` — the content-addressed
        ``DataStore`` layer — asks the store rather than sniffing SDK types
        itself. The default recognises nothing, so an unknown backend
        propagates every error unchanged.
        """
        return False

    @staticmethod
    def _closed_error(class_name: str) -> ConnectorClosedError:
        """Build the typed error for "used after close" — call sites ``raise`` it.

        Mirrors
        :meth:`pirn.connectors.connector_base.ConnectorBase._closed_error`
        for the ``ObjectStore`` hierarchy, which does not share
        ``ConnectorBase``.
        """
        return ConnectorClosedError(f"{class_name} is closed")

    def _validate_key(self, key: str) -> None:
        """Reject keys that would cause path-traversal or invalid byte issues.

        Shared by every concrete store. Subclasses call this from ``get`` /
        ``put`` / ``delete`` before issuing the underlying request.
        Rejects:

        * empty keys,
        * NUL bytes (which would corrupt logs and downstream parsers),
        * leading ``/`` (always a caller mistake on object stores that use
          relative-style keys),
        * any ``..`` path segment (path traversal protection).
        """
        if not key:
            raise ValueError("key must be non-empty")
        if "\x00" in key:
            raise ValueError("key contains NUL byte")
        if key.startswith("/"):
            raise ValueError("key must not start with '/'")
        parts = key.split("/")
        if any(p == ".." for p in parts):
            raise ValueError("key must not contain '..' segments")
