"""``InMemorySessionStore`` — a zero-dependency in-process :class:`SessionStore`.

.. deprecated:: ADR agents-speaks-core WS3 part 2
    See :mod:`pirn_agents.sessions.session_store` and
    :mod:`pirn_agents.sessions.session_chain`.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence

from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from pirn_agents.sessions.session_store import SessionStore


class InMemorySessionStore(SessionStore):
    """A dict-backed reference :class:`SessionStore` for tests and single-process runs."""

    def __init__(self) -> None:
        """Initialise an empty store."""
        warnings.warn(
            "InMemorySessionStore is deprecated (ADR agents-speaks-core WS3): "
            "see pirn_agents.sessions.session_chain.SessionChain.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._checkpoints: dict[str, RunCheckpoint] = {}

    async def save(self, session_id: str, checkpoint: RunCheckpoint) -> None:
        """Persist ``checkpoint`` as the latest state for ``session_id``.

        Raises:
            TypeError: If ``checkpoint`` is not a RunCheckpoint.
        """
        if not isinstance(checkpoint, RunCheckpoint):
            raise TypeError(
                f"InMemorySessionStore: checkpoint must be a RunCheckpoint, "
                f"got {type(checkpoint).__name__}"
            )
        self._checkpoints[session_id] = checkpoint

    async def load(self, session_id: str) -> RunCheckpoint | None:
        """Return the latest checkpoint for ``session_id``, or ``None``."""
        return self._checkpoints.get(session_id)

    async def delete(self, session_id: str) -> None:
        """Remove the stored checkpoint for ``session_id`` if present."""
        self._checkpoints.pop(session_id, None)

    async def list_sessions(self) -> Sequence[str]:
        """Return the sorted ids of all sessions with a stored checkpoint."""
        return sorted(self._checkpoints)

    async def close(self) -> None:
        """Drop all stored checkpoints."""
        self._checkpoints.clear()
