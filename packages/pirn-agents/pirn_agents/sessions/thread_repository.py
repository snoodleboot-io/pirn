"""``ThreadRepository`` — durable, session-keyed persistence for conversation threads.

Persists a :class:`ConversationThread` through an injected F4
:class:`~pirn_agents.memory.stores.memory_store.MemoryStore`, keyed by the thread's stable
``session_id``. Because the thread round-trips through the store's untyped mapping
payload, a thread survives process restarts: a fresh repository over the same
durable backend re-reads a prior thread. The repository names no vendor and imports
no driver — any lazy backend import lives in the concrete ``MemoryStore``.

.. deprecated:: ADR agents-speaks-core WS3 part 2
    A session's message history is now exactly what
    :meth:`~pirn_agents.sessions.run_state.RunState.from_chain` projects from
    its run chain (:mod:`pirn_agents.sessions.session_chain`) — the engine
    already durably records it, so a separate keyed thread store is
    redundant. Kept for one cycle for callers still writing explicit threads.
"""

from __future__ import annotations

import warnings

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.sessions.conversation_thread import ConversationThread


class ThreadRepository:
    """Save and load durable :class:`ConversationThread`s by session id."""

    def __init__(self, *, store: MemoryStore, key_prefix: str = "thread") -> None:
        """Bind the repository to a backing ``MemoryStore`` and key namespace.

        Args:
            store: The F4 memory store threads are persisted through.
            key_prefix: Namespace prefix for every thread key. Non-empty.

        Raises:
            TypeError: If ``store`` is not a MemoryStore.
            ValueError: If ``key_prefix`` is empty.
        """
        warnings.warn(
            "ThreadRepository is deprecated (ADR agents-speaks-core WS3): "
            "see pirn_agents.sessions.run_state.RunState.from_chain.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"ThreadRepository: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not key_prefix:
            raise ValueError("ThreadRepository: key_prefix must be non-empty")
        self._store = store
        self._key_prefix = key_prefix

    def _key(self, session_id: str) -> str:
        """Return the backing-store key for ``session_id``."""
        return f"{self._key_prefix}:{session_id}"

    async def save(self, thread: ConversationThread) -> None:
        """Persist ``thread`` under its session id.

        Raises:
            TypeError: If ``thread`` is not a ConversationThread.
        """
        if not isinstance(thread, ConversationThread):
            raise TypeError(
                f"ThreadRepository: thread must be a ConversationThread, "
                f"got {type(thread).__name__}"
            )
        await self._store.store(self._key(thread.session_id), thread.to_payload())

    async def load(self, session_id: str) -> ConversationThread | None:
        """Return the durable thread for ``session_id``, or ``None`` if absent."""
        payload = await self._store.retrieve(self._key(session_id))
        if payload is None:
            return None
        return ConversationThread.from_payload(payload)

    async def delete(self, session_id: str) -> None:
        """Remove the stored thread for ``session_id`` if present."""
        await self._store.forget(self._key(session_id))
