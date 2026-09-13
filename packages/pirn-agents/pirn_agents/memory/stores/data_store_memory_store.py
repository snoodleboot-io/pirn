"""``DataStoreMemoryStore`` — the plain key-value :class:`MemoryStore` (PIR-787).

Before this adapter the only concrete :class:`MemoryStore` implementations were
the ``VectorMemoryStore`` family, whose ``store()`` requires a ``"vector"``
entry and raises ``KeyError`` on any other mapping. Every *keyed* consumer —
``PersistedSessionStore``, ``ThreadRepository``, ``MemoryWriter``,
``SemanticMemoryUpsert``, ``CrossSessionProfileUpdater`` — therefore had no
shipped backend to run against.

ADR "agents speaks core" WS3 part 4: a caller-chosen key is a knot id, not a
row in a hashed key-value table. This adapter's ``store``/``retrieve``/
``forget`` now delegate to
:class:`~pirn_agents.memory.stores.keyed_lineage_store.KeyedLineageStore`,
which writes each value as a single-knot ``Tapestry`` run (the engine
content-addresses it into ``DataStore`` and records one ``KnotLineage`` row)
and reads "the current value under this key" via
``RunHistory.query_latest_lineage_by_knot_id``. The ``content_hash(key)``
method that used to fabricate a fake content hash by hashing the caller's
*key* — inverting what a ``DataStore`` hash means, since a hash stopped
identifying a value and started identifying a caller-chosen name — is gone;
there is no longer a hash to compute from a bare key at all.

**Missing keys are not errors.** ``KeyedLineageStore.get`` already returns
``None`` for an absent (or evicted) key, matching the ``MemoryStore``
contract with no translation needed here.

Similarity :meth:`search` is *not* implemented: a key-value backend has no
notion of nearness. Use a ``VectorMemoryStore`` when you need search.

Backend-neutral by construction: nothing here imports a vendor driver, and the
injected ``DataStore`` owns whatever lazy import it needs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.run_history import RunHistory
from pirn.backends.base.value_retention import ValueRetention
from pirn.backends.in_memory.in_memory_history import InMemoryHistory

from pirn_agents.memory.stores.keyed_lineage_store import KeyedLineageStore
from pirn_agents.memory.stores.memory_store import MemoryStore


class DataStoreMemoryStore(MemoryStore):
    """A keyed :class:`MemoryStore` backed by any core :class:`DataStore`, via lineage."""

    def __init__(
        self,
        *,
        data_store: DataStore,
        namespace: str = "agent-memory",
        history: RunHistory | None = None,
    ) -> None:
        """Bind the adapter to a backing ``DataStore``/``RunHistory`` and key namespace.

        Args:
            data_store: The core data store values are content-addressed
                into. Any shipped implementation works (in-memory, disk, S3,
                GCS, Azure, ValKey); durability and signing are the backend's
                concern.
            namespace: Prefix folded into every keyed identity so that
                several logical stores can share one backend without
                colliding. Non-empty.
            history: The ``RunHistory`` each write is recorded to and each
                read is served from. Defaults to a private, per-instance
                ``InMemoryHistory`` — pass a durable, shared backend for keys
                that must survive past this process or be visible to another
                one.

        Raises:
            TypeError: If ``data_store`` is not a ``DataStore`` or ``history``
                is not a ``RunHistory``.
            ValueError: If ``namespace`` is empty.
        """
        if not isinstance(data_store, DataStore):
            raise TypeError(
                f"DataStoreMemoryStore: data_store must be a DataStore, "
                f"got {type(data_store).__name__}"
            )
        if history is not None and not isinstance(history, RunHistory):
            raise TypeError(
                f"DataStoreMemoryStore: history must be a RunHistory, got {type(history).__name__}"
            )
        if not namespace:
            raise ValueError("DataStoreMemoryStore: namespace must be non-empty")
        self._data_store = data_store
        self._namespace = namespace
        self._keyed = KeyedLineageStore(
            history=history if history is not None else InMemoryHistory(),
            data_store=data_store,
        )

    @property
    def namespace(self) -> str:
        """The prefix folded into every keyed identity."""
        return self._namespace

    @property
    def retention(self) -> ValueRetention:
        """Delegate to the wrapped ``DataStore``'s declared ceiling.

        This adapter adds no bound of its own on the value plane — every key
        it writes is content-addressed straight into ``data_store`` — so its
        retention is exactly the backend's. A bounded backend (e.g. the
        default ``InMemoryDataStore``) evicts values from underneath this
        store the same way it would any other; see :meth:`retrieve`.
        """
        return self._data_store.retention

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        """Persist a snapshot of ``value`` under ``key``.

        Args:
            key: The logical key — becomes a knot id
                (``KeyedLineageStore.identity``), not a hashed row.
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
        await self._keyed.put(namespace=self._namespace, key=key, value=dict(value))

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        """Return the current value stored under ``key``, or ``None`` if absent.

        Args:
            key: The logical key passed to :meth:`store`.

        Returns:
            The stored mapping, or ``None``.

        Note:
            ``None`` covers eviction too. A backend whose ``retention``
            declares a ``max_values`` ceiling — the default
            ``InMemoryDataStore`` does, at 10,000 values — drops its least
            recently used entries and raises ``ValueEvictedError`` when the
            corresponding value has been evicted, which
            :meth:`KeyedLineageStore.get` already translates to ``None``. See
            PIR-839.
        """
        return await self._keyed.get(namespace=self._namespace, key=key)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
    ) -> Sequence[Mapping[str, Any]]:
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
        """Remove the entry stored under ``key``; missing keys are a no-op write.

        Writes a tombstone (see :meth:`KeyedLineageStore.delete`) rather than
        erasing anything — there is no "unrecord a run" operation, so the
        prior value's lineage rows stay in ``RunHistory`` for anyone who
        wants them; ordinary readers just see ``key`` as absent from now on.
        """
        await self._keyed.delete(namespace=self._namespace, key=key)

    async def close(self) -> None:
        """Scrub credentials. The injected ``DataStore`` owns its own lifecycle.

        Core's ``DataStore`` interface has no ``close()``: connection lifetime
        belongs to whoever constructed the backend, which may be shared with
        the engine's own value cache. Closing it here would tear down a
        resource this adapter does not own.
        """
        self._clear_credentials()
