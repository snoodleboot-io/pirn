from __future__ import annotations

from typing import Any


class DataStore:
    """Interface: where intermediate values live, keyed by content hash.

    Lineage references values by hash; the data store holds them by hash.
    Scrubbing values from the data store does not affect lineage.

    Implementations inherit from this class and override all methods.
    """

    async def put(self, content_hash: str, value: Any) -> None:
        """Persist a value under its content hash.

        Args:
            content_hash: SHA-256 hex digest (with or without ``sha256:`` prefix)
                that uniquely identifies the serialized value.
            value: Arbitrary Python object to store.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement put()")

    async def get(self, content_hash: str) -> Any:
        """Retrieve a value by its content hash.

        Args:
            content_hash: Hash previously passed to :meth:`put`.

        Returns:
            The stored value.

        Raises:
            KeyError: If no value is stored under ``content_hash``.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement get()")

    async def has(self, content_hash: str) -> bool:
        """Return ``True`` if a value is stored under ``content_hash``.

        Args:
            content_hash: Hash to check.

        Returns:
            ``True`` if present, ``False`` otherwise.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement has()")

    async def scrub(self, content_hash: str) -> None:
        """Remove a value.  Lineage referencing it remains intact."""
        raise NotImplementedError(f"{type(self).__name__} must implement scrub()")
