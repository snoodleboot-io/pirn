"""``_BatchItemStreamer`` — hands each batch item's outcome to ``MapAgent.run`` as it settles.

ADR agents-speaks-core, WS0b. ``MapAgent`` joins its per-item knots through
a core ``Aggregator``, which only produces its combined value once *every*
item has settled — so the standalone ``async for result in map_agent.run(...)``
stream could only yield the whole batch at the end of the run. Core's
:meth:`~pirn.emitters.emitter.Emitter.on_knot_result` fires inside the
engine loop the instant each knot settles, with its full ``Result`` and
lineage row, so this emitter is what restores the pre-migration streaming
contract: it translates every item knot's outcome into a
:class:`~pirn_agents.batch.batch_item_result.BatchItemResult` and puts it on
the queue ``run`` is draining, while the join is still waiting for the rest.

Algorithm:
    On ``on_knot_result(knot_id, result, lineage)``:

    1. Ignore any knot whose id is not one of this batch's item ids (the
       aggregator, a resumed-batch parameter, knots of other emitters'
       runs).
    2. Look up the item's ``(index, key)`` by knot id.
    3. Build ``BatchItemResult(index, key, outcome=result,
       attempts=lineage.extra["attempts"], latency=lineage.duration_ms /
       1000)`` — the lineage row is what carries the attempt count and the
       wall-clock, which the aggregator's ``Result``-only combine could not
       populate.
    4. ``put_nowait`` it on the queue; the queue is unbounded, so the hook
       never blocks the engine.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from pirn.emitters.emitter import Emitter

from pirn_agents.batch.batch_item_result import BatchItemResult

if TYPE_CHECKING:
    from pirn.core.knot_lineage import KnotLineage
    from pirn.core.result import Result


class _BatchItemStreamer(Emitter):
    """Streams a batch's per-item ``BatchItemResult``s onto a queue as they settle."""

    def __init__(
        self,
        *,
        items_by_knot_id: dict[str, tuple[int, str]],
        queue: asyncio.Queue[BatchItemResult | None],
    ) -> None:
        """Bind the streamer to one batch.

        Args:
            items_by_knot_id: The batch's live item knot ids mapped to the
                ``(index, key)`` each ``BatchItemResult`` reports.
            queue: Where each settled item's result is put. ``MapAgent.run``
                drains it and reads ``None`` as "the run is over".
        """
        self._items_by_knot_id = dict(items_by_knot_id)
        self._queue = queue

    async def on_knot_result(self, knot_id: str, result: Result[Any], lineage: KnotLineage) -> None:
        located = self._items_by_knot_id.get(knot_id)
        if located is None:
            return
        index, key = located
        attempts = lineage.extra.get("attempts", 1)
        self._queue.put_nowait(
            BatchItemResult(
                index=index,
                key=key,
                outcome=result,
                attempts=attempts if isinstance(attempts, int) else 1,
                latency=lineage.duration_ms / 1000.0,
            )
        )
