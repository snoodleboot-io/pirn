"""``BatchCheckpointer`` — persist/restore batch progress over an F14 store.

A thin adapter that lets a batch resume where it stopped by reusing F14's durable
session machinery *as-is*: it saves a :class:`BatchProgress` by projecting it onto
a :class:`~pirn_agents.sessions.run_state.RunState`, content-addressing it into a
:class:`~pirn_agents.sessions.run_checkpoint.RunCheckpoint`, and writing it to the
injected :class:`~pirn_agents.sessions.session_store.SessionStore` — the same
store type an agent run checkpoints to. On restart, :meth:`load` reads the latest
checkpoint back into a :class:`BatchProgress` so already-completed items are
skipped. No batch-specific persistence backend is introduced.

The ``batch_id`` is the whole of the namespace: two runs sharing one id share
one skip-set. :meth:`scoped` derives a *sibling* checkpointer under a narrower
id, which is how a repeating batch keeps each occurrence's resume state
separate while still resuming within an occurrence (PIR-803).
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

    def scoped(self, suffix: str) -> BatchCheckpointer:
        """Return a sibling checkpointer namespaced under ``"<batch_id>-<suffix>"``.

        The same store, a narrower key. A batch that runs repeatedly — once per
        trigger fire, say — resumes correctly *within* one occurrence by using
        one stable suffix for it, while a different suffix keeps the next
        occurrence's skip-set entirely separate. Without that, an item key
        repeating across occurrences (a customer id, a partition key) is read as
        already-done and silently skipped.

        The suffix is percent-escaped before being joined, so the mapping from
        suffix to namespace is injective (PIR-813). Without that, two different
        suffixes could name one namespace and silently share a skip-set — and
        the case is not hypothetical now that a caller may name a window with a
        timestamp: ``2026-08-16`` and ``2026`` + ``08-16`` would otherwise both
        land on ``<batch_id>-2026-08-16``.

        Args:
            suffix: The scope discriminator, e.g. a fire ordinal or a window
                identity. Must be non-empty and stable for the occurrence it
                names, since it *is* the resume key. Any character is allowed;
                the escaping keeps the namespace unambiguous.

        Returns:
            A new ``BatchCheckpointer`` over this one's store.

        Raises:
            ValueError: If ``suffix`` is not a non-empty ``str``.
        """
        if not isinstance(suffix, str) or not suffix:
            raise ValueError("BatchCheckpointer.scoped: suffix must be a non-empty str")
        # `%` first, or escaping `-` would itself become escapable input.
        escaped = suffix.replace("%", "%25").replace("-", "%2D")
        return BatchCheckpointer(store=self._store, batch_id=f"{self._batch_id}-{escaped}")

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
