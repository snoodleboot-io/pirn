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

Lifecycle: this trigger is **single-use**, because :meth:`close` is terminal —
it refuses further :meth:`fire` calls, so a stream that has run to its end can
never be fed again. Re-streaming a spent trigger therefore raises instead of
parking forever on a queue nothing can refill; construct a new ``EventTrigger``
per run. The queue is shared by every live stream, so two concurrent consumers
*compete* for signals (each fire reaches exactly one of them) — end-of-stream is
the one signal that broadcasts, so closing releases all of them.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger


class EventTrigger(Trigger):
    """Fire once per externally-signalled event until closed.

    Single-use: ``close()`` is terminal, so a spent trigger refuses both
    :meth:`fire` and a new :meth:`stream` rather than deadlocking a caller who
    reuses it. Concurrent consumers share one queue and so split the signals
    between them; only end-of-stream reaches all of them.
    """

    def __init__(self) -> None:
        """Create an idle trigger with an empty signal queue."""
        self._queue: asyncio.Queue[bool] = asyncio.Queue()
        self._closed = False
        self._ended = False

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
        consumer would otherwise mistake for a live signal. The one sentinel is
        re-armed by whichever consumer takes it, so end-of-stream reaches every
        live consumer rather than only the first.

        Terminal: :meth:`fire` is refused afterwards and :meth:`stream` raises
        once the stream has run out, so a closed trigger cannot be reused.
        """
        if self._closed:
            return
        self._closed = True
        self._queue.put_nowait(False)

    def stream(self) -> AsyncIterator[RunRequest]:
        """Return a stream yielding one ``RunRequest`` per fire signal.

        Closing is **terminal**: this trigger is single-use, because ``close()``
        can only queue one end-of-stream signal and a consumer eats it. Once a
        stream has run to that end, re-streaming raises rather than parking
        forever on a queue that can never be fed again — ``fire()`` is closed
        too. Signals queued before ``close()`` are still drained first, so
        fire/fire/close/stream reports both fires.

        Returns:
            An async iterator of ``RunRequest``, each carrying the 1-based
            ``fire_ordinal`` of the signal that produced it.

        Raises:
            RuntimeError: If this trigger's stream has already run to its end.
        """
        if self._ended:
            raise RuntimeError(
                "EventTrigger: this trigger's stream has already ended, so a new "
                "stream would block forever — close() is terminal and fire() is "
                "refused afterwards. Construct a new EventTrigger per run."
            )
        return self._drain()

    async def _drain(self) -> AsyncIterator[RunRequest]:
        """Drain the signal queue until the end-of-stream signal arrives.

        Yields:
            A ``RunRequest`` whose ``parameters`` carry the 1-based
            ``fire_ordinal`` of the signal that produced it.
        """
        ordinal = 0
        while True:
            live = await self._queue.get()
            if not live:
                self._ended = True
                # Put the end-of-stream signal back. close() can only queue one,
                # so without this the *first* consumer to see it strands every
                # other consumer parked in get() forever — and a queue nothing
                # can refill, since fire() is refused once closed. Re-arming
                # makes end-of-stream broadcast to all consumers instead of
                # being delivered to exactly one.
                self._queue.put_nowait(False)
                return
            ordinal += 1
            yield RunRequest(parameters={"fire_ordinal": ordinal})
