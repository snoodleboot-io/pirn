from __future__ import annotations

from typing import Any


class DataStore:
    """Interface: where intermediate values live, keyed by content hash.

    Lineage references values by hash; the data store holds them by hash.
    Scrubbing values from the data store does not affect lineage.

    Implementations inherit from this class and override all methods.
    """

    async def put(self, content_hash: str, value: Any) -> None:
        raise NotImplementedError(f"{type(self).__name__} must implement put()")

    async def get(self, content_hash: str) -> Any:
        raise NotImplementedError(f"{type(self).__name__} must implement get()")

    async def has(self, content_hash: str) -> bool:
        raise NotImplementedError(f"{type(self).__name__} must implement has()")

    async def scrub(self, content_hash: str) -> None:
        """Remove a value.  Lineage referencing it remains intact."""
        raise NotImplementedError(f"{type(self).__name__} must implement scrub()")
