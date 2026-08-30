"""``DataStoreMemoryStore`` — the plain key-value :class:`MemoryStore` (PIR-787).

Before this adapter the only concrete :class:`MemoryStore` implementations were
the ``VectorMemoryStore`` family, whose ``store()`` requires a ``"vector"``
entry and raises ``KeyError`` on any other mapping. Every *keyed* consumer —
``PersistedSessionStore``, ``ThreadRepository``, ``MemoryWriter``,
``SemanticMemoryUpsert``, ``CrossSessionProfileUpdater`` — therefore had no
shipped backend to run against.

This adapter closes that gap by wrapping any core
:class:`pirn.backends.base.data_store.DataStore` (in-memory, local disk, S3,
GCS, Azure, ValKey), which is exactly a keyed put/get/has/scrub surface. Two
details make the mapping honest:

* **Keys are hashed before they reach the backend.** A ``DataStore`` key is a
  content hash, and backends turn it into a filename or object key —
  ``LocalDiskDataStore`` would otherwise try to write a file called
  ``session:s1``. Hashing ``namespace`` + ``key`` into a SHA-256 hex digest
  keeps every agent key safe, deterministic across processes, and namespaced so
  two logical stores can share one backend without colliding.
* **Missing keys are not errors.** ``DataStore.get`` raises ``KeyError``;
  the :class:`MemoryStore` contract returns ``None``.

Similarity :meth:`search` is *not* implemented: a key-value backend has no
notion of nearness. Use a ``VectorMemoryStore`` when you need search.

Backend-neutral by construction: nothing here imports a vendor driver, and the
injected ``DataStore`` owns whatever lazy import it needs.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.backends.base.data_store import DataStore

from pirn_agents.memory.stores.memory_store import MemoryStore


class DataStoreMemoryStore(MemoryStore):
    """A keyed :class:`MemoryStore` backed by any core :class:`DataStore`."""

    def __init__(self, *, data_store: DataStore, namespace: str = "agent-memory") -> None:
        """Bind the adapter to a backing ``DataStore`` and key namespace.

        Args:
            data_store: The core data store values are persisted through. Any
                shipped implementation works (in-memory, disk, S3, GCS, Azure,
                ValKey); durability and signing are the backend's concern.
            namespace: Prefix folded into every hashed key so that several
                logical stores can share one backend without colliding.
                Non-empty.

        Raises:
            TypeError: If ``data_store`` is not a ``DataStore``.
            ValueError: If ``namespace`` is empty.
        """
        if not isinstance(data_store, DataStore):
            raise TypeError(
                f"DataStoreMemoryStore: data_store must be a DataStore, "
                f"got {type(data_store).__name__}"
            )
        if not namespace:
            raise ValueError("DataStoreMemoryStore: namespace must be non-empty")
        self._data_store = data_store
        self._namespace = namespace

    @property
    def namespace(self) -> str:
        """The prefix folded into every hashed key."""
        return self._namespace

    def content_hash(self, key: str) -> str:
        """Return the backend key a logical ``key`` maps to.

        The digest covers the namespace and the key, separated by a NUL byte so
        that ``("a", "b:c")`` and ``("a:b", "c")`` cannot collide. Backends key
        objects by content hash and derive filenames or object keys from it, so
        a raw agent key such as ``"session:s1"`` must never reach them.

        Args:
            key: The logical key used by the caller.

        Returns:
            A 64-character SHA-256 hex digest, stable across processes.
        """
        digest = hashlib.sha256()
        digest.update(self._namespace.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(key.encode("utf-8"))
        return digest.hexdigest()

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        """Persist a snapshot of ``value`` under ``key``.

        Args:
            key: The logical key; hashed before it reaches the backend.
            value: Any mapping. Unlike a vector store, no particular entry is
                required. A shallow copy is taken so later caller mutations do
                not rewrite stored state.

        Raises:
            TypeError: If ``value`` is not a mapping.
        """
        if not isinstance(value, Mapping):
            raise TypeError(
                f"DataStoreMemoryStore: value must be a Mapping, got {type(value).__name__}"
            )
        await self._data_store.put(self.content_hash(key), dict(value))

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        """Return the value stored under ``key``, or ``None`` if absent.

        Args:
            key: The logical key passed to :meth:`store`.

        Returns:
            The stored mapping, or ``None``. The backend's ``KeyError`` for a
            missing hash is translated to ``None`` per the ``MemoryStore``
            contract.

        Note:
            That translation covers eviction too. A backend whose
            ``retention`` declares a ``max_values`` ceiling — the default
            ``InMemoryDataStore`` does, at 10,000 values — drops its least
            recently used entries and raises ``ValueEvictedError``, which is a
            ``KeyError``, so a long session silently reads ``None`` for memory
            it wrote earlier. That is the ``MemoryStore`` contract working as
            designed: a memory store reports absence, it does not promise
            durability the way a lineage row does. Give a session whose memory
            must survive a durable ``DataStore``, or raise the ceiling. See
            PIR-839.
        """
        try:
            return await self._data_store.get(self.content_hash(key))
        except KeyError:
            return None

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Always raise: a key-value backend cannot answer similarity queries.

        Args:
            query: Ignored.
            top_k: Ignored.

        Raises:
            NotImplementedError: Always. ``DataStoreMemoryStore`` wraps a
                content-addressed key-value backend, not a vector index.
        """
        raise NotImplementedError(
            "DataStoreMemoryStore.search() is not supported: it wraps a key-value "
            "DataStore, which has no similarity index. Use a VectorMemoryStore "
            "(in-memory, pgvector, Qdrant, Chroma) for search()."
        )

    async def forget(self, key: str) -> None:
        """Remove the entry stored under ``key``; missing keys are a no-op."""
        await self._data_store.scrub(self.content_hash(key))

    async def close(self) -> None:
        """Scrub credentials. The injected ``DataStore`` owns its own lifecycle.

        Core's ``DataStore`` interface has no ``close()``: connection lifetime
        belongs to whoever constructed the backend, which may be shared with
        the engine's own value cache. Closing it here would tear down a
        resource this adapter does not own.
        """
        self._clear_credentials()
