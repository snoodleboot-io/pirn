"""``RunResumer`` — rehydrate a persisted run so only its tail is replayed.

Algorithm:
    1. Load the session's latest :class:`RunCheckpoint` from the store.
    2. If absent, return ``None`` (nothing to resume).
    3. Otherwise return its :class:`RunState`. The state's
       :meth:`RunState.remaining_plan` is the uncomputed tail the caller replays;
       completed steps (below the cursor) are never recomputed.

The resumer is a pure read: it performs no writes, so repeated ``resume`` calls
on the same session are idempotent and produce no duplicate side effects.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_store import SessionStore


class RunResumer(Knot):
    """Rehydrate a persisted :class:`RunState` from a :class:`SessionStore`."""

    def __init__(
        self,
        *,
        store: Knot | SessionStore,
        session_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(store=store, session_id=session_id, _config=_config, **kwargs)

    async def process(
        self,
        store: SessionStore,
        session_id: str,
        **_: Any,
    ) -> RunState | None:
        """Return the persisted run state for ``session_id``, or ``None``.

        Args:
            store: The session store to read from.
            session_id: The session to rehydrate.

        Returns:
            The rehydrated :class:`RunState`, or ``None`` when no checkpoint
            exists for ``session_id``.

        Raises:
            TypeError: If ``store`` is not a SessionStore or ``session_id`` is not
                a non-empty str.
        """
        if not isinstance(store, SessionStore):
            raise TypeError(f"RunResumer: store must be a SessionStore, got {type(store).__name__}")
        if not isinstance(session_id, str) or not session_id:
            raise TypeError("RunResumer: session_id must be a non-empty str")
        checkpoint = await store.load(session_id)
        if checkpoint is None:
            return None
        return checkpoint.state
