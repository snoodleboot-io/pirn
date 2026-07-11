"""``BlobStore`` — provider-neutral object/blob storage interface (F16-S4 / PIR-363).

A minimal, streaming get/put/list contract that both the local-filesystem
backend and the S3-compatible backend satisfy, so ingestion (F25) and durable
sessions (F14) depend only on this interface, never a concrete backend.

Streaming is intrinsic to the contract: :meth:`get` returns an async byte-chunk
iterator and :meth:`put` consumes one, so a whole object is never required to be
resident in memory. Backend selection is configuration-driven and each concrete
backend lazily imports its driver.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class BlobStore(PirnOpaqueValue):
    """Interface every object/blob storage backend must satisfy."""

    def get(self, key: str) -> AsyncIterator[bytes]:
        """Return an async iterator streaming the object's bytes chunk-by-chunk."""
        raise NotImplementedError(f"{type(self).__name__} must implement get()")

    async def put(self, key: str, data: AsyncIterator[bytes]) -> None:
        """Stream ``data`` into the object at ``key`` without buffering it whole."""
        raise NotImplementedError(f"{type(self).__name__} must implement put()")

    async def list(self, prefix: str = "") -> Sequence[str]:
        """Return the keys under ``prefix`` (all keys when ``prefix`` is empty)."""
        raise NotImplementedError(f"{type(self).__name__} must implement list()")

    async def close(self) -> None:
        """Release any pooled backend resources. Default is a no-op."""
        return None
