"""``EventTrigger`` — an on-demand batch trigger (PIR-723 / WS8-D2).

A core :class:`pirn.triggers.base.Trigger` that fires when an external event
arrives: a caller (a webhook handler, a queue consumer, a test) awaits
:meth:`fire` to enqueue a fire signal, and the consumer — a
:class:`~pirn_agents.batch.triggered_batch.TriggeredBatch`, or core's
``run_forever`` against a tapestry — gets one ``RunRequest`` per signal.
:meth:`close` ends the stream so the consumer loop exits cleanly.

Built on an in-process :class:`asyncio.Queue`; no message-broker backend is
imported. This is the in-process *source* — a genuinely external source is a
core trigger of its own (``KafkaTrigger``, ``ValKeyTrigger``, ``WebhookTrigger``)
and drives the same consumer directly, or is wired here by calling :meth:`fire`
from its handler.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger


class EventTrigger(Trigger):
    """Fire once per externally-signalled event until closed."""

    def __init__(self) -> None:
        """Create an idle trigger with an empty signal queue."""
        self._queue: asyncio.Queue[bool] = asyncio.Queue()
        self._closed = False

    @property
    def name(self) -> str:
        """Human-readable identifier for this trigger."""
        return "EventTrigger"

    async def fire(self) -> None:
        """Enqueue one fire signal.

        Raises:
            RuntimeError: If the trigger has already been closed.
        """
        if self._closed:
            raise RuntimeError("EventTrigger: cannot fire a closed trigger")
        await self._queue.put(True)

    async def close(self) -> None:
        """Signal end-of-stream so :meth:`stream` stops draining.

        Idempotent: a second call queues no second sentinel, which a later
        consumer would otherwise mistake for a live signal.
        """
        if self._closed:
            return
        self._closed = True
        self._queue.put_nowait(False)

    async def stream(self) -> AsyncIterator[RunRequest]:
        """Yield one ``RunRequest`` per received fire signal until closed.

        Yields:
            A ``RunRequest`` whose ``parameters`` carry the 1-based
            ``fire_ordinal`` of the signal that produced it.
        """
        ordinal = 0
        while True:
            live = await self._queue.get()
            if not live:
                return
            ordinal += 1
            yield RunRequest(parameters={"fire_ordinal": ordinal})
