"""``SessionStore`` — the provider-neutral durable-session persistence interface.

.. deprecated:: ADR agents-speaks-core WS3 part 2
    A session is a chain of engine runs now (see
    :mod:`pirn_agents.sessions.session_chain`); the engine's own
    ``RunHistory``/``DataStore`` already durably record every turn, so nothing
    needs a separate keyed checkpoint store. This interface and its concrete
    implementations (:class:`~pirn_agents.sessions.in_memory_session_store.InMemorySessionStore`,
    :class:`~pirn_agents.sessions.persisted_session_store.PersistedSessionStore`)
    stay importable for one cycle for callers that have not migrated.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.sessions.run_checkpoint import RunCheckpoint


class SessionStore(PirnOpaqueValue):
    """Interface every durable-session store must satisfy.

    A session store persists the latest :class:`RunCheckpoint` for a session,
    keyed by ``session_id``. Implementations may keep state in-process or delegate
    to a persisted backend; knots depend only on this interface.
    """

    async def save(self, session_id: str, checkpoint: RunCheckpoint) -> None:
        """Persist ``checkpoint`` as the latest state for ``session_id``."""
        raise NotImplementedError(f"{type(self).__name__} must implement save()")

    async def load(self, session_id: str) -> RunCheckpoint | None:
        """Return the latest checkpoint for ``session_id``, or ``None``."""
        raise NotImplementedError(f"{type(self).__name__} must implement load()")

    async def delete(self, session_id: str) -> None:
        """Remove the stored checkpoint for ``session_id`` if present."""
        raise NotImplementedError(f"{type(self).__name__} must implement delete()")

    async def list_sessions(self) -> Sequence[str]:
        """Return the ids of all sessions with a stored checkpoint."""
        raise NotImplementedError(f"{type(self).__name__} must implement list_sessions()")

    async def close(self) -> None:
        """Release any underlying resources. Default is a no-op."""
        return None
