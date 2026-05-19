from __future__ import annotations

from threading import Lock
from typing import Any

from pirn.backends.base.data_store import DataStore


class InMemoryDataStore(DataStore):
    """In-memory DataStore.

    Holds intermediate values keyed by content hash.  Scrubbing is
    immediate and irreversible.
    """

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._lock = Lock()

    async def put(self, content_hash: str, value: Any) -> None:
        """Store a value under its content hash.

        Args:
            content_hash: Content-addressable key for the value.
            value: Arbitrary Python object to store.
        """
        with self._lock:
            self._values[content_hash] = value

    async def get(self, content_hash: str) -> Any:
        """Retrieve a value by its content hash.

        Args:
            content_hash: Hash previously passed to :meth:`put`.

        Returns:
            The stored Python object.

        Raises:
            KeyError: If no value is stored under ``content_hash``.
        """
        with self._lock:
            if content_hash not in self._values:
                raise KeyError(content_hash)
            return self._values[content_hash]

    async def has(self, content_hash: str) -> bool:
        """Return ``True`` if a value is stored under ``content_hash``.

        Args:
            content_hash: Hash to check.

        Returns:
            ``True`` if present, ``False`` otherwise.
        """
        with self._lock:
            return content_hash in self._values

    async def scrub(self, content_hash: str) -> None:
        """Remove the value stored under ``content_hash``, if present.

        Args:
            content_hash: Hash of the value to remove.
        """
        with self._lock:
            self._values.pop(content_hash, None)
