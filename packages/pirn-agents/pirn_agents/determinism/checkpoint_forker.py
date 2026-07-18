"""``CheckpointForker`` — fork a new run from an F14 checkpoint for what-if runs."""

from __future__ import annotations

from pirn_agents.determinism.fork_result import ForkResult
from pirn_agents.sessions.execution_cursor import ExecutionCursor
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_store import SessionStore


class CheckpointForker:
    """Branch a new run from any recorded F14 checkpoint, preserving prior trace.

    Loads the source session's latest :class:`RunCheckpoint` from a
    :class:`SessionStore`, rebuilds its :class:`RunState` under a fresh
    ``new_session_id``, optionally rewinds the plan cursor to a ``fork_point`` so
    the branch diverges only from that step onward, persists the forked checkpoint
    back into the store, and returns a :class:`ForkResult` whose provenance makes
    the fork distinguishable from the original.
    """

    async def fork(
        self,
        *,
        store: SessionStore,
        source_session_id: str,
        new_session_id: str,
        fork_point: int | None = None,
    ) -> ForkResult:
        """Fork ``source_session_id`` into ``new_session_id`` at ``fork_point``.

        Args:
            store: The session store holding the source checkpoint and receiving
                the forked one.
            source_session_id: The run to branch from.
            new_session_id: The id for the divergent branch.
            fork_point: Plan step index to diverge from; ``None`` forks at the
                source's current cursor. Prior completed steps are preserved.

        Returns:
            The :class:`ForkResult` with the new checkpoint and its provenance.

        Raises:
            TypeError: If ``store`` is not a SessionStore.
            ValueError: If no checkpoint exists for ``source_session_id`` or
                ``fork_point`` is negative / past the plan length.
        """
        if not isinstance(store, SessionStore):
            raise TypeError(
                f"CheckpointForker.fork: store must be a SessionStore, got {type(store).__name__}"
            )
        source = await store.load(source_session_id)
        if source is None:
            raise ValueError(
                f"CheckpointForker.fork: no checkpoint for source session {source_session_id!r}"
            )
        forked_state = self._rewind(source.state, new_session_id, fork_point)
        forked = RunCheckpoint.create(forked_state)
        await store.save(new_session_id, forked)
        return ForkResult(
            new_session_id=new_session_id,
            source_session_id=source_session_id,
            forked_from_checkpoint_id=source.checkpoint_id,
            fork_point=forked_state.cursor.step_index,
            checkpoint=forked,
        )

    @staticmethod
    def _rewind(state: RunState, new_session_id: str, fork_point: int | None) -> RunState:
        """Return ``state`` re-keyed to ``new_session_id`` and rewound to fork point."""
        if fork_point is None:
            cursor = state.cursor
        else:
            if fork_point < 0 or fork_point > len(state.plan):
                raise ValueError(
                    f"CheckpointForker.fork: fork_point {fork_point} out of range "
                    f"[0, {len(state.plan)}]"
                )
            cursor = ExecutionCursor(
                step_index=fork_point,
                completed_steps=state.cursor.completed_steps[:fork_point],
            )
        return RunState(
            session_id=new_session_id,
            messages=state.messages,
            plan=state.plan,
            tool_results=state.tool_results,
            cursor=cursor,
        )
