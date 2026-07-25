"""``BatchCheckpointer`` — persist/restore batch progress over an F14 store.

A thin adapter that lets a batch resume where it stopped by reusing F14's durable
session machinery *as-is*: it saves a :class:`BatchProgress` by projecting it onto
a :class:`~pirn_agents.sessions.run_state.RunState`, content-addressing it into a
:class:`~pirn_agents.sessions.run_checkpoint.RunCheckpoint`, and writing it to the
injected :class:`~pirn_agents.sessions.session_store.SessionStore` — the same
store type an agent run checkpoints to. On restart, :meth:`load` reads the latest
checkpoint back into a :class:`BatchProgress` so already-completed items are
skipped. No batch-specific persistence backend is introduced.
"""

from __future__ import annotations

from pirn_agents.batch.batch_progress import BatchProgress
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from pirn_agents.sessions.session_store import SessionStore


class BatchCheckpointer:
    """Save/restore a batch's :class:`BatchProgress` through an F14 SessionStore."""

    def __init__(self, *, store: SessionStore, batch_id: str) -> None:
        """Build the checkpointer.

        Args:
            store: The F14 durable-session store the checkpoint is persisted to.
            batch_id: Stable id keying this batch's state in the store.

        Raises:
            TypeError: If ``store`` is not a SessionStore.
            ValueError: If ``batch_id`` is empty.
        """
        if not isinstance(store, SessionStore):
            raise TypeError(
                f"BatchCheckpointer: store must be a SessionStore, got {type(store).__name__}"
            )
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError("BatchCheckpointer: batch_id must be a non-empty str")
        self._store = store
        self._batch_id = batch_id

    @property
    def batch_id(self) -> str:
        """The batch id this checkpointer persists under."""
        return self._batch_id

    async def load(self) -> BatchProgress:
        """Return the persisted progress, or empty progress when none exists yet."""
        checkpoint = await self._store.load(self._batch_id)
        if checkpoint is None:
            return BatchProgress(batch_id=self._batch_id)
        return BatchProgress.from_run_state(checkpoint.state)

    async def save(self, progress: BatchProgress) -> None:
        """Persist ``progress`` as the latest checkpoint for this batch.

        The progress is projected onto an F14 :class:`RunState` and
        content-addressed into a :class:`RunCheckpoint`, so writing identical
        progress twice is a no-op-equivalent (the store keys by batch id and the
        checkpoint id is stable).

        Raises:
            TypeError: If ``progress`` is not a BatchProgress, or its ``batch_id``
                does not match this checkpointer's.
        """
        if not isinstance(progress, BatchProgress):
            raise TypeError(
                f"BatchCheckpointer: progress must be a BatchProgress, "
                f"got {type(progress).__name__}"
            )
        if progress.batch_id != self._batch_id:
            raise TypeError(
                f"BatchCheckpointer: progress.batch_id {progress.batch_id!r} does not match "
                f"checkpointer batch_id {self._batch_id!r}"
            )
        checkpoint = RunCheckpoint.create(progress.to_run_state())
        await self._store.save(self._batch_id, checkpoint)
