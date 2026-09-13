"""``RunCheckpointer`` — persist a run's state at a safe point, content-addressed.

.. deprecated:: ADR agents-speaks-core WS3 part 2
    The active session model no longer writes a ``RunCheckpoint`` blob — a
    turn's own ``RunResult`` is already durably recorded, and
    :class:`~pirn_agents.sessions.run_resumer.RunResumer` projects the current
    :class:`~pirn_agents.sessions.run_state.RunState` straight from the run
    chain (:mod:`pirn_agents.sessions.session_chain`). Kept for one cycle for
    callers still writing explicit checkpoints.

Algorithm:
    1. Content-address the incoming :class:`RunState` into a :class:`RunCheckpoint`.
    2. Load the session's current checkpoint. If its ``checkpoint_id`` already
       matches the new one, the state is unchanged — skip the write (dedup) and
       return the existing checkpoint. This makes repeated checkpoints of an
       unchanged run idempotent (no duplicate writes / side effects).
    3. Otherwise persist the new checkpoint and return it.
"""

from __future__ import annotations

import warnings
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_store import SessionStore


class RunCheckpointer(Knot):
    """Persist a :class:`RunState` to a :class:`SessionStore` with dedup."""

    def __init__(
        self,
        *,
        store: Knot | SessionStore,
        state: Knot | RunState,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(store=store, state=state, _config=_config, **kwargs)

    async def process(
        self,
        store: SessionStore,
        state: RunState,
        **_: Any,
    ) -> RunCheckpoint:
        """Checkpoint ``state`` into ``store`` at a safe point, deduplicating.

        Args:
            store: The session store the checkpoint is persisted to.
            state: The run state to capture.

        Returns:
            The persisted (or already-present, deduplicated) :class:`RunCheckpoint`.
        """
        warnings.warn(
            "RunCheckpointer is deprecated (ADR agents-speaks-core WS3): "
            "a turn's RunResult is already durably recorded — see "
            "pirn_agents.sessions.session_chain.SessionChain and "
            "pirn_agents.sessions.run_resumer.RunResumer.",
            DeprecationWarning,
            stacklevel=2,
        )
        checkpoint = RunCheckpoint.create(state)
        existing = await store.load(state.session_id)
        if existing is not None and existing.checkpoint_id == checkpoint.checkpoint_id:
            return existing
        await store.save(state.session_id, checkpoint)
        return checkpoint
