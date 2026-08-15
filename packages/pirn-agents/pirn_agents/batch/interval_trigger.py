"""``IntervalTrigger`` — a scheduled batch trigger (PIR-723 / WS8-D2).

A core :class:`pirn.triggers.base.Trigger` that fires on a schedule: by default
every ``interval`` seconds, optionally bounded by ``max_fires``. The schedule is
pluggable through ``delay_fn`` — a ``Callable[[int], float]`` mapping the next
1-based fire ordinal to the seconds to wait before it — which is the seam an
external **cron** backend fills (a croniter/APScheduler-derived "seconds until
next cron instant" function drops straight in) without this module importing any
scheduler. The async ``sleep`` is injected so tests advance the schedule
deterministically with no wall-clock wait.

The schedule itself is not implemented here: it is delegated wholesale to
:class:`pirn.triggers.cron.CronTrigger`'s ``delay_fn`` mode, whose contract
("wait ``fn(ordinal)`` seconds before each fire, ordinal 1 included") is exactly
this class's. Constant-interval mode is expressed as a constant ``delay_fn``
rather than as ``CronTrigger(every_seconds=...)`` deliberately: ``every_seconds``
mode yields its *first* request immediately, whereas an interval batch must wait
one window before its first run so that run has a window's worth of data to
process. Delegating through ``delay_fn`` keeps that wait-then-fire semantic and
still reuses core's loop and close handling. The ``RunRequest`` is rebuilt here
rather than taken from the delegate, because the fire ordinal has to be per
stream and the delegate's ``parameters_factory`` seam is zero-argument and so
cannot tell two streams apart.

Lifecycle: every :meth:`~IntervalTrigger.stream` call is independent — its own
ordinals, its own ``max_fires`` budget — so a trigger that has run out of fires
is reusable and can drive another batch. :meth:`~IntervalTrigger.close` is the
one shared, and terminal, operation: it ends every live stream and makes any
later ``stream()`` raise, rather than hand back an empty stream that reads like
a schedule which merely has not fired yet.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger
from pirn.triggers.cron import CronTrigger


class IntervalTrigger(Trigger):
    """Fire on a fixed interval or an injected per-fire delay schedule.

    Re-streamable: each :meth:`stream` numbers its own fires from 1 and gets its
    own ``max_fires`` budget, so sequential and concurrent consumers never share
    a counter. :meth:`close` is terminal and applies to the whole trigger, so a
    caller that wants to run the schedule again must simply not close it.
    """

    def __init__(
        self,
        *,
        interval: float | None = None,
        delay_fn: Callable[[int], float] | None = None,
        max_fires: int | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """Configure the schedule.

        Args:
            interval: Constant seconds to wait before each fire, the first
                included. Mutually exclusive with ``delay_fn``; exactly one must
                be given.
            delay_fn: Maps the next 1-based fire ordinal to the seconds to wait
                before it — the cron seam. Mutually exclusive with ``interval``.
                Every returned delay is awaited, ordinal 1's included and zero
                or negative ones included: :func:`asyncio.sleep` treats those as
                no wait, a cron backend may legitimately return a negative when
                the instant it computed has just passed, and awaiting
                unconditionally keeps a collapsed schedule from busy-spinning.
            max_fires: Stop after this many fires; ``None`` runs unbounded. Must
                be an ``int``; a non-integral bound such as ``2.5`` is rejected
                rather than silently truncated at the fire that crosses it.
            sleep: Async sleep used before each fire; injected in tests. Defaults
                to :func:`asyncio.sleep` inside the delegate.

        Raises:
            ValueError: If neither or both of ``interval``/``delay_fn`` are given,
                ``interval`` is negative, or ``max_fires`` is not an ``int`` >= 1.
        """
        if (interval is None) == (delay_fn is None):
            raise ValueError("IntervalTrigger: give exactly one of interval or delay_fn")
        if interval is not None and interval < 0:
            raise ValueError(f"IntervalTrigger: interval must be >= 0, got {interval!r}")
        # Validated here, before delegating, so a bad value is reported against
        # the parameter the caller actually passed rather than the delegate's
        # ``max_runs``. The int check is what the delegate would have applied.
        if max_fires is not None and (
            isinstance(max_fires, bool) or not isinstance(max_fires, int) or max_fires < 1
        ):
            raise ValueError(f"IntervalTrigger: max_fires must be an int >= 1, got {max_fires!r}")
        # Only consulted when ``delay_fn`` is absent, i.e. when ``interval`` was
        # supplied and validated non-negative.
        self._interval: float = 0.0 if interval is None else interval
        self._closed = False
        self._cron = CronTrigger(
            delay_fn=delay_fn if delay_fn is not None else self._constant_delay,
            max_runs=max_fires,
            sleep=sleep,
        )

    @property
    def name(self) -> str:
        """Human-readable identifier for this trigger."""
        return "IntervalTrigger"

    def stream(self) -> AsyncIterator[RunRequest]:
        """Yield one ``RunRequest`` per fire, waiting the scheduled delay first.

        Each call returns an **independent** stream that numbers its own fires
        from 1 and gets its own ``max_fires`` budget, so a trigger may be
        re-streamed (sequentially or concurrently) without two consumers sharing
        a counter. Only :meth:`close` is shared: it ends every live stream.

        Returns:
            A fresh request stream; each request carries its 1-based
            ``fire_ordinal`` in ``parameters``.

        Raises:
            RuntimeError: If :meth:`close` has been called. Closing is terminal,
                and a closed trigger's stream would otherwise end immediately
                and report nothing, which is indistinguishable from a schedule
                that simply has not fired yet.
        """
        if self._closed:
            raise RuntimeError(
                "IntervalTrigger: this trigger is closed, so a new stream would "
                "yield nothing. Closing is terminal; construct a new "
                "IntervalTrigger rather than re-streaming a closed one."
            )
        return self._numbered_stream()

    async def _numbered_stream(self) -> AsyncIterator[RunRequest]:
        """Re-number a fresh delegate stream from a per-call ordinal.

        The delegate owns the schedule, the ``max_fires`` bound and close
        handling; the ordinal is kept here, as a local of this generator rather
        than on the instance, because that is what makes two streams
        independent. The delegate's own ``RunRequest`` is discarded: it carries
        no parameters, so rebuilding is cheaper than threading a per-stream
        counter through the shared ``parameters_factory`` seam, which is
        zero-argument and so cannot tell the streams apart.

        Yields:
            One ``RunRequest`` per fire, carrying this stream's 1-based
            ``fire_ordinal``.
        """
        ordinal = 0
        async for _ in self._cron.stream():
            ordinal += 1
            yield RunRequest(parameters={"fire_ordinal": ordinal})

    async def close(self) -> None:
        """Stop the schedule; no further ``RunRequest`` is emitted. Idempotent.

        Terminal: it ends every live stream and bars new ones. A caller that
        wants the schedule to pause and resume should simply not close it —
        a stream that has exhausted ``max_fires`` leaves the trigger reusable.
        """
        self._closed = True
        await self._cron.close()

    def _constant_delay(self, ordinal: int) -> float:
        """Return the fixed interval, ignoring the ordinal.

        Args:
            ordinal: 1-based index of the fire about to be emitted; unused,
                since every fire in constant-interval mode waits the same.

        Returns:
            The configured ``interval`` in seconds.
        """
        return self._interval
