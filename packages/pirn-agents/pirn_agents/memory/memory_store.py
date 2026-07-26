"""Interface for asynchronous agent memory stores.

A :class:`MemoryStore` provides keyed write/read plus similarity
search; concrete implementations may wrap a vector database, a
document store, an in-memory dict, or a hybrid. Pirn agent knots
depend only on this interface; the store is constructed by the user
and passed in as a config value.

Pydantic treats stores as opaque (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
identity-keyed serialiser keeps content-addressing cache stable
without descending into vendor SDKs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class MemoryStore(PirnOpaqueValue):
    """Interface every async memory store must satisfy."""

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        """Persist ``value`` under ``key``."""
        raise NotImplementedError(f"{type(self).__name__} must implement store()")

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        """Return the value previously stored under ``key``, or ``None``."""
        raise NotImplementedError(f"{type(self).__name__} must implement retrieve()")

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Yield up to ``top_k`` mappings most similar to ``query``."""
        raise NotImplementedError(f"{type(self).__name__} must implement search()")

    async def forget(self, key: str) -> None:
        """Remove the entry stored under ``key`` if present."""
        raise NotImplementedError(f"{type(self).__name__} must implement forget()")

    async def close(self) -> None:
        """Release any underlying connections / resources."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")

    def _clear_credentials(self) -> None:
        """Drop the in-memory credential reference held by the store.

        Concrete implementations should call this from ``close()`` after
        tearing down the live SDK / client. It nulls ``self._config`` so
        the credential string (token, api key, secret) becomes garbage-
        collectable as soon as the caller drops the store reference.
        Long-running processes that hold store references after
        ``close()`` benefit; default deployments are unaffected.
        """
        self._config = None
