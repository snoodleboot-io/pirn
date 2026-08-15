"""``MemoryStoreKeyIndex`` — a serialised key index over a ``MemoryStore`` (PIR-720).

Core's ``DataStore`` is content-hash-keyed: it can put, get, has and scrub a
single hash, but it cannot enumerate. Any agent store that must answer "which
keys do I hold?" therefore has to maintain the answer itself, in a record it
writes alongside the data. ``PersistedSessionStore`` was the first to need this
and hand-rolled it inline; this class is that logic extracted so the next
enumerating store inherits a correct implementation instead of re-deriving a
subtly wrong one.

The correctness problem is that maintaining such a record is a read-modify-write.
Read the list, append your key, write it back — and if another coroutine did the
same thing in between, your write erases theirs. The interleaving window is not
theoretical: every shipped backend awaits real I/O in the middle of it
(``LocalDiskDataStore`` hands file reads and writes to ``asyncio.to_thread``,
the object stores and ValKey await the network), so concurrent writers reliably
all read the same stale list. The affected key's *data* is stored correctly and
still loads; it simply disappears from enumeration.

Every mutation here is therefore serialised behind an :class:`asyncio.Lock`.

**What that lock does and does not buy you.** An :class:`asyncio.Lock` serialises
coroutines on one event loop in one process, and that is all. It does *not* make
the index safe against a second process, a second host, or a second instance of
this class over the same backend record — each holds its own lock and neither
sees the other's. Deployments that write one logical index from several
processes need the backend itself to provide atomicity (a compare-and-set, a
conditional write, or a row lock); this class cannot supply it and does not
pretend to. Within a single agent process — the shape every current consumer
has — it is sufficient.
"""

from __future__ import annotations

import asyncio

from pirn_agents.memory.stores.memory_store import MemoryStore


class MemoryStoreKeyIndex:
    """A set of keys persisted in one ``MemoryStore`` record, safe to mutate concurrently."""

    def __init__(self, *, store: MemoryStore, index_key: str, field: str = "keys") -> None:
        """Bind the index to a backing store, its record key, and its payload field.

        Args:
            store: The memory store the index record lives in. The index is one
                ordinary record in the same store as the data it indexes, so it
                inherits that backend's durability and nothing more.
            index_key: The key the index record is stored under. Must not
                collide with a key being indexed. Non-empty.
            field: Name of the entry inside the record holding the key list.
                Injectable because the field name is part of the on-disk format:
                a store with indexes already persisted must keep reading and
                writing the name it wrote them under. Non-empty.

        Raises:
            TypeError: If ``store`` is not a :class:`MemoryStore`.
            ValueError: If ``index_key`` or ``field`` is empty.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"MemoryStoreKeyIndex: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not index_key:
            raise ValueError("MemoryStoreKeyIndex: index_key must be non-empty")
        if not field:
            raise ValueError("MemoryStoreKeyIndex: field must be non-empty")
        self._store = store
        self._index_key = index_key
        self._field = field
        self._lock = asyncio.Lock()

    @property
    def index_key(self) -> str:
        """The backing-store key the index record is written to."""
        return self._index_key

    @property
    def field(self) -> str:
        """The entry inside the index record that holds the key list."""
        return self._field

    async def keys(self) -> list[str]:
        """Return the indexed keys in insertion order.

        Reads take the lock as well as writes, so a caller never observes the
        state a half-finished mutation is about to replace.

        An absent record, a record without the configured field, and a record
        whose field does not hold a list or tuple all read as empty rather than
        raising: an index is derived convenience state, and a store that has
        never been written to simply holds nothing. That shape check is
        deliberate, not incidental. Iterating the field directly would accept a
        string and yield one key per character, so a record corrupted to
        ``{"keys": "abc"}`` would enumerate as ``["a", "b", "c"]`` — a plausible
        key list a caller cannot tell from a real one. Entries inside a
        well-shaped list are coerced with ``str``.

        Returns:
            A fresh list the caller may mutate without affecting the index.
        """
        async with self._lock:
            return await self._read()

    async def add(self, key: str) -> None:
        """Add ``key`` to the index if it is not already present.

        The read and the write happen under one lock hold, so a concurrent
        :meth:`add` or :meth:`remove` cannot slip in between them and lose this
        edit.

        Args:
            key: The key to index. Adding a key already present is a no-op and
                writes nothing.
        """
        async with self._lock:
            current = await self._read()
            if key in current:
                return
            await self._write([*current, key])

    async def remove(self, key: str) -> None:
        """Remove ``key`` from the index if present.

        Args:
            key: The key to de-index. Removing an absent key is a no-op and
                writes nothing.
        """
        async with self._lock:
            current = await self._read()
            if key not in current:
                return
            await self._write([entry for entry in current if entry != key])

    async def _read(self) -> list[str]:
        """Return the persisted key list. Caller must hold the lock."""
        record = await self._store.retrieve(self._index_key)
        if record is None:
            return []
        entries = record.get(self._field)
        if not isinstance(entries, (list, tuple)):
            return []
        return [str(entry) for entry in entries]

    async def _write(self, keys: list[str]) -> None:
        """Overwrite the persisted key list. Caller must hold the lock."""
        await self._store.store(self._index_key, {self._field: keys})
