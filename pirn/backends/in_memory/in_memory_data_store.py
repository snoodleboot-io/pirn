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
        with self._lock:
            self._values[content_hash] = value

    async def get(self, content_hash: str) -> Any:
        with self._lock:
            if content_hash not in self._values:
                raise KeyError(content_hash)
            return self._values[content_hash]

    async def has(self, content_hash: str) -> bool:
        with self._lock:
            return content_hash in self._values

    async def scrub(self, content_hash: str) -> None:
        with self._lock:
            self._values.pop(content_hash, None)
