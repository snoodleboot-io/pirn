"""``PersistedSessionStore`` — a :class:`SessionStore` over an F4 ``MemoryStore``.

The persisted adapter delegates every operation to an injected
:class:`~pirn_agents.memory_store.MemoryStore`, so it is inherently
backend-neutral: no vendor is named here and no driver is imported. The optional
backend (chroma / pgvector / qdrant, …) is lazily imported *inside the concrete
``MemoryStore``*, so ``import pirn_agents`` — and importing this adapter — stays
backend-free. Checkpoints round-trip through the store's untyped mapping payload
via :meth:`RunCheckpoint.to_payload` / :meth:`RunCheckpoint.from_payload`.

A small key index (stored under :attr:`_index_key`) tracks the live session ids so
:meth:`list_sessions` never has to scan the whole backend.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn_agents.memory_store import MemoryStore
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from pirn_agents.sessions.session_store import SessionStore


class PersistedSessionStore(SessionStore):
    """A durable :class:`SessionStore` backed by any :class:`MemoryStore`."""

    def __init__(self, *, store: MemoryStore, key_prefix: str = "session") -> None:
        """Bind the adapter to a backing ``MemoryStore`` and key namespace.

        Args:
            store: The F4 memory store checkpoints are persisted through.
            key_prefix: Namespace prefix for every session key. Non-empty.

        Raises:
            TypeError: If ``store`` is not a MemoryStore.
            ValueError: If ``key_prefix`` is empty.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"PersistedSessionStore: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not key_prefix:
            raise ValueError("PersistedSessionStore: key_prefix must be non-empty")
        self._store = store
        self._key_prefix = key_prefix
        self._index_key = f"{key_prefix}:__index__"

    def _key(self, session_id: str) -> str:
        """Return the backing-store key for ``session_id``."""
        return f"{self._key_prefix}:{session_id}"

    async def _index(self) -> list[str]:
        """Return the current list of live session ids from the index record."""
        record = await self._store.retrieve(self._index_key)
        if record is None:
            return []
        return [str(sid) for sid in record.get("session_ids", [])]

    async def _write_index(self, session_ids: Sequence[str]) -> None:
        """Persist the live-session-id index."""
        await self._store.store(self._index_key, {"session_ids": list(session_ids)})

    async def save(self, session_id: str, checkpoint: RunCheckpoint) -> None:
        """Persist ``checkpoint`` for ``session_id`` and index the id.

        Raises:
            TypeError: If ``checkpoint`` is not a RunCheckpoint.
        """
        if not isinstance(checkpoint, RunCheckpoint):
            raise TypeError(
                f"PersistedSessionStore: checkpoint must be a RunCheckpoint, "
                f"got {type(checkpoint).__name__}"
            )
        await self._store.store(self._key(session_id), checkpoint.to_payload())
        index = await self._index()
        if session_id not in index:
            await self._write_index([*index, session_id])

    async def load(self, session_id: str) -> RunCheckpoint | None:
        """Return the latest checkpoint for ``session_id``, or ``None``."""
        payload = await self._store.retrieve(self._key(session_id))
        if payload is None:
            return None
        return RunCheckpoint.from_payload(payload)

    async def delete(self, session_id: str) -> None:
        """Remove the checkpoint for ``session_id`` and de-index the id."""
        await self._store.forget(self._key(session_id))
        index = await self._index()
        if session_id in index:
            await self._write_index([sid for sid in index if sid != session_id])

    async def list_sessions(self) -> Sequence[str]:
        """Return the sorted ids of all sessions with a stored checkpoint."""
        return sorted(await self._index())

    async def close(self) -> None:
        """Release the backing store's resources."""
        await self._store.close()
