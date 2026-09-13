"""``BatchScheduler`` — the bounded dispatch/checkpoint loop behind :class:`MapAgent`.

Extracted from :class:`~pirn_agents.batch.map_agent.MapAgent` (PIR-856, SRP) to
separate the *scheduling* concern (pull items lazily, keep at most ``limit()``
in flight, stream results as they settle, persist checkpoints, drain cleanly on
cancellation) from the *per-item execution* concern that stays on ``MapAgent``
(retry policy, rate limiting, adaptive concurrency feedback, error/timeout
wrapping).

The scheduler is intentionally not provider-neutral in the "any dataset" sense
but *agent*-neutral: it drives whatever ``run_one`` coroutine callable it is
given, exactly the shape ``MapAgent`` already builds from its own
``_run_one``. It holds no agent-specific state itself.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable

from pirn_agents.batch.batch_checkpointer import BatchCheckpointer
from pirn_agents.batch.batch_item_result import BatchItemResult
from pirn_agents.batch.batch_item_status import BatchItemStatus
from pirn_agents.batch.batch_progress import BatchProgress


class BatchScheduler:
    """Bounded, checkpointing, completion-order dispatch loop for a batch run."""

    def __init__(
        self,
        *,
        run_one: Callable[[int, object, str, frozenset[str]], Awaitable[BatchItemResult]],
        key_for: Callable[[int, object], str],
        limit: Callable[[], int],
        drain_on_cancel: Callable[[set[asyncio.Task[BatchItemResult]]], Awaitable[None]],
        checkpointer: BatchCheckpointer | None,
        checkpoint_every: int,
    ) -> None:
        """Wire the scheduler to its collaborators.

        Args:
            run_one: Runs one item to a terminal :class:`BatchItemResult`,
                never raising except :class:`asyncio.CancelledError` — the
                same contract ``MapAgent._run_one`` implements.
            key_for: Maps ``(index, item)`` to the item's stable resume key.
            limit: Returns the current dispatch bound (may vary over the
                run's lifetime under an adaptive controller).
            drain_on_cancel: Awaits every still-pending task so cancellation
                never leaks a running item; the same contract
                ``AsyncFanoutEngine.drain_on_cancel`` implements.
            checkpointer: The (already scope-narrowed) checkpointer this run
                persists through, or ``None`` to disable checkpointing.
            checkpoint_every: Persist after this many newly-completed items.
        """
        self._run_one = run_one
        self._key_for = key_for
        self._limit = limit
        self._drain_on_cancel = drain_on_cancel
        self._checkpointer = checkpointer
        self._checkpoint_every = checkpoint_every

    async def run(self, inputs: Iterable[object]) -> AsyncIterator[BatchItemResult]:
        """Run ``inputs`` through ``run_one``, yielding each result as it settles.

        Args:
            inputs: The dataset to map over. Consumed lazily — one item is
                pulled only when an in-flight slot is free — so the stream is
                never materialised in full and backpressure flows to the
                producer.

        Yields:
            One :class:`BatchItemResult` per input item, in completion order.

        Raises:
            asyncio.CancelledError: Propagated (after draining in-flight
                items) if the generator is cancelled.
        """
        checkpointer = self._checkpointer
        progress = await self._load_progress(checkpointer)
        # Held as a local, not on the instance: it belongs to this run, and a
        # scheduler is deliberately reusable across runs (PIR-803).
        completed_keys = progress.completed_keys
        source = enumerate(inputs)
        pending: set[asyncio.Task[BatchItemResult]] = set()
        exhausted = False
        since_checkpoint = 0
        try:
            while True:
                exhausted = self._fill(source, pending, exhausted, completed_keys)
                if not pending:
                    break
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    result = task.result()
                    if checkpointer is not None and result.status is BatchItemStatus.OK:
                        progress = progress.with_completed(result.key)
                        since_checkpoint += 1
                        if since_checkpoint >= self._checkpoint_every:
                            await checkpointer.save(progress)
                            since_checkpoint = 0
                    yield result
        except asyncio.CancelledError:
            await self._drain_on_cancel(pending)
            raise
        if checkpointer is not None and since_checkpoint > 0:
            await checkpointer.save(progress)

    @staticmethod
    async def _load_progress(checkpointer: BatchCheckpointer | None) -> BatchProgress:
        """Load prior progress (seeding the resume skip-set), or start empty."""
        if checkpointer is None:
            return BatchProgress(batch_id="batch")
        return await checkpointer.load()

    def _fill(
        self,
        source: object,
        pending: set[asyncio.Task[BatchItemResult]],
        exhausted: bool,
        completed_keys: frozenset[str],
    ) -> bool:
        """Top up ``pending`` up to the current limit, returning exhaustion.

        Pulls at most enough items to reach ``limit()`` in-flight; each pull is
        the lazy ``next()`` that carries backpressure to the input producer.
        """
        if exhausted:
            return True
        while len(pending) < self._limit():
            try:
                index, item = next(source)  # type: ignore[call-overload]
            except StopIteration:
                return True
            key = self._key_for(index, item)
            pending.add(asyncio.ensure_future(self._run_one(index, item, key, completed_keys)))
        return False
