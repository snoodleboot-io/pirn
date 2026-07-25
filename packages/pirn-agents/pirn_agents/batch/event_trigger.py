"""``EventTrigger`` — an on-demand batch trigger (F28-S5 / PIR-584).

Fires when an external event arrives: a caller (a webhook handler, a queue
consumer, a test) awaits :meth:`fire` to enqueue a fire signal, and the bound
:class:`~pirn_agents.batch.triggered_batch.TriggeredBatch` runs one batch per
signal. :meth:`close` ends the stream so the consumer loop exits cleanly. Built
on an in-process :class:`asyncio.Queue`; no message-broker backend is imported —
an external event source is wired by calling :meth:`fire` from its handler.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from pirn_agents.batch.batch_trigger import BatchTrigger


class EventTrigger(BatchTrigger):
    """Fire once per externally-signalled event until closed."""

    def __init__(self) -> None:
        """Create an idle trigger with an empty signal queue."""
        self._queue: asyncio.Queue[bool] = asyncio.Queue()
        self._closed = False

    async def fire(self) -> None:
        """Enqueue one fire signal.

        Raises:
            RuntimeError: If the trigger has already been closed.
        """
        if self._closed:
            raise RuntimeError("EventTrigger: cannot fire a closed trigger")
        await self._queue.put(True)

    def close(self) -> None:
        """Signal end-of-stream; the :meth:`fires` iterator stops draining."""
        self._closed = True
        self._queue.put_nowait(False)

    async def fires(self) -> AsyncIterator[int]:
        """Yield a 1-based ordinal per received fire signal until closed."""
        ordinal = 0
        while True:
            live = await self._queue.get()
            if not live:
                return
            ordinal += 1
            yield ordinal
