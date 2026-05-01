"""Interface for async object stores (S3, GCS, Azure Blob, local filesystem).

Reads stream as :class:`AsyncIterator[bytes]` so the connector never needs
to load a full object into memory.
"""

from __future__ import annotations

from typing import AsyncIterator

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class ObjectStore(PirnOpaqueValue):
    """Interface every connector object-store implementation must satisfy.

    Implementations:
      - :class:`pirn.domains.connectors.object_storage.local_filesystem_store.LocalFilesystemStore`
      - :class:`pirn.domains.connectors.object_storage.s3_store.S3Store`

    Pydantic treats stores as opaque (see
    :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
    identity-keyed serialiser keeps content-addressing cache stable
    without descending into engine internals (boto3, gcs, ...).
    """

    async def get(self, key: str) -> AsyncIterator[bytes]:
        """Stream the bytes of the object at ``key``."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement get()"
        )

    async def put(
        self, key: str, body: AsyncIterator[bytes] | bytes
    ) -> None:
        """Write ``body`` to ``key`` — bytes or an async iterator of bytes."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement put()"
        )

    async def delete(self, key: str) -> None:
        """Remove the object at ``key``. Idempotent."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement delete()"
        )

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        """Yield all keys under ``prefix`` in lexicographic order."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement list()"
        )

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

