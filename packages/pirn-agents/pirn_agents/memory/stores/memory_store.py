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

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.backends.base.value_retention import ValueRetention
from pirn.core.pirn_opaque_value import PirnOpaqueValue


class MemoryStore(PirnOpaqueValue):
    """Interface every async memory store must satisfy."""

    @property
    def retention(self) -> ValueRetention:
        """Declare how many entries this store promises to keep.

        Mirrors :attr:`pirn.backends.base.data_store.DataStore.retention` and
        :attr:`pirn.backends.base.run_history.RunHistory.retention`: rather
        than a caller asking what *class* a store is before deciding whether
        it needs to bound growth itself, the store declares its own ceiling
        (``None`` — the default here — for a durable, unbounded backend).

        ADR "agents speaks core" WS3 folds ``MemoryEvictor`` +
        ``MemoryEvictionPolicy`` eviction into this same capability rather
        than adding a fourth bounding mechanism alongside ``DataStore``,
        ``RunHistory``, and the context layer's ``EvictionPolicy``: a store
        backed by a bounded backend overrides this to report that ceiling
        (:class:`~pirn_agents.memory.stores.data_store_memory_store.DataStoreMemoryStore`
        does, delegating to its wrapped ``DataStore``). ``MemoryEvictor`` and
        :class:`~pirn_agents.memory.management.low_value_eviction_policy.LowValueEvictionPolicy`
        remain the explicit, importance x recency-scored eviction knot for
        callers who hold a batch of typed
        :class:`~pirn_agents.memory.management.memory_record.MemoryRecord` and
        want to select victims themselves; ``retention`` is the store-level
        declaration for the generic keyed-mapping path, where no such typed
        batch exists to score.
        """
        return ValueRetention()

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
    ) -> Sequence[Mapping[str, Any]]:
        """Return up to ``top_k`` mappings most similar to ``query``, most similar first.

        The contract is a single ``await`` away from a concrete, len()-able
        sequence — never an async iterator or generator. Every caller can
        therefore write ``results = await store.search(...)`` with no
        duck-typed drain for "was that awaitable, async-iterable, or already
        a list?" (PIR-856; the ambiguity previously forced 8 near-identical
        drain copies across the RAG/guardrail/memory call sites).
        """
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
