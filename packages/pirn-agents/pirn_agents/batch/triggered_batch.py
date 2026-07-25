"""``TriggeredBatch`` — run a batch once per trigger fire (F28-S5 / PIR-584).

Binds a :class:`~pirn_agents.batch.batch_trigger.BatchTrigger` to a
:class:`~pirn_agents.batch.map_agent.MapAgent`: for each fire it fetches a fresh
input set from ``inputs_fn(ordinal)``, runs the batch to completion, and yields a
:class:`~pirn_agents.batch.batch_progress.BatchProgress` summarising that run
(``completed_count`` successes out of ``total`` — the partial-failure report per
fire). It owns no scheduling itself; the trigger decides *when* and this decides
*what*, so a cron/interval schedule and an event source drive the same batch with
no code change.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterable

from pirn_agents.batch.batch_progress import BatchProgress
from pirn_agents.batch.batch_trigger import BatchTrigger
from pirn_agents.batch.map_agent import MapAgent


class TriggeredBatch:
    """Drive a :class:`MapAgent` once per fire of a :class:`BatchTrigger`."""

    def __init__(
        self,
        *,
        trigger: BatchTrigger,
        map_agent: MapAgent,
        inputs_fn: Callable[[int], Iterable[object]],
        batch_id: str = "batch",
    ) -> None:
        """Bind the trigger, runner, and per-fire input source.

        Args:
            trigger: The fire source.
            map_agent: The configured batch runner invoked on each fire.
            inputs_fn: Maps a 1-based fire ordinal to that run's input items —
                called fresh per fire so each run can pick up new data.
            batch_id: Stable prefix for each run's reported batch id
                (``"<batch_id>-<ordinal>"``).

        Raises:
            TypeError: If ``trigger``/``map_agent`` are the wrong type or
                ``inputs_fn`` is not callable.
            ValueError: If ``batch_id`` is empty.
        """
        if not isinstance(trigger, BatchTrigger):
            raise TypeError(
                f"TriggeredBatch: trigger must be a BatchTrigger, got {type(trigger).__name__}"
            )
        if not isinstance(map_agent, MapAgent):
            raise TypeError(
                f"TriggeredBatch: map_agent must be a MapAgent, got {type(map_agent).__name__}"
            )
        if not callable(inputs_fn):
            raise TypeError(
                f"TriggeredBatch: inputs_fn must be callable, got {type(inputs_fn).__name__}"
            )
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError("TriggeredBatch: batch_id must be a non-empty str")
        self._trigger = trigger
        self._map_agent = map_agent
        self._inputs_fn = inputs_fn
        self._batch_id = batch_id

    async def run(self) -> AsyncIterator[BatchProgress]:
        """Run one batch per fire, yielding a :class:`BatchProgress` per run."""
        async for ordinal in self._trigger.fires():
            inputs = self._inputs_fn(ordinal)
            completed: set[str] = set()
            total = 0
            async for result in self._map_agent.run(inputs):
                total += 1
                if result.succeeded:
                    completed.add(result.key)
            yield BatchProgress(
                batch_id=f"{self._batch_id}-{ordinal}",
                completed_keys=frozenset(completed),
                total=total,
            )
