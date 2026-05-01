"""Interface for async object stores (S3, GCS, Azure Blob, local filesystem).

Reads stream as :class:`AsyncIterator[bytes]` so the connector never needs
to load a full object into memory.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class ObjectStore:
    """Interface every connector object-store implementation must satisfy.

    Implementations:
      - :class:`pirn.domains.connectors.object_storage.local_filesystem_store.LocalFilesystemStore`
      - :class:`pirn.domains.connectors.object_storage.s3_store.S3Store`
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

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat object stores as opaque.

        Concrete stores wrap engine-specific clients (boto3, gcs, …) that
        are not pydantic-compatible.
        """
        return core_schema.is_instance_schema(cls)
