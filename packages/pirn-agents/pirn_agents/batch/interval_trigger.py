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
still reuses core's loop, close handling and ``RunRequest`` construction.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger
from pirn.triggers.cron import CronTrigger


class IntervalTrigger(Trigger):
    """Fire on a fixed interval or an injected per-fire delay schedule."""

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
            max_fires: Stop after this many fires; ``None`` runs unbounded.
            sleep: Async sleep used before each fire; injected in tests. Defaults
                to :func:`asyncio.sleep` inside the delegate.

        Raises:
            ValueError: If neither or both of ``interval``/``delay_fn`` are given,
                ``interval`` is negative, or ``max_fires`` < 1.
        """
        if (interval is None) == (delay_fn is None):
            raise ValueError("IntervalTrigger: give exactly one of interval or delay_fn")
        if interval is not None and interval < 0:
            raise ValueError(f"IntervalTrigger: interval must be >= 0, got {interval!r}")
        if max_fires is not None and (isinstance(max_fires, bool) or max_fires < 1):
            raise ValueError(f"IntervalTrigger: max_fires must be an int >= 1, got {max_fires!r}")
        # Only consulted when ``delay_fn`` is absent, i.e. when ``interval`` was
        # supplied and validated non-negative.
        self._interval: float = 0.0 if interval is None else interval
        self._fired = 0
        self._cron = CronTrigger(
            delay_fn=delay_fn if delay_fn is not None else self._constant_delay,
            parameters_factory=self._next_parameters,
            max_runs=max_fires,
            sleep=sleep,
        )

    @property
    def name(self) -> str:
        """Human-readable identifier for this trigger."""
        return "IntervalTrigger"

    def stream(self) -> AsyncIterator[RunRequest]:
        """Yield one ``RunRequest`` per fire, waiting the scheduled delay first.

        Returns:
            The delegate's request stream; each request carries its 1-based
            ``fire_ordinal`` in ``parameters``.
        """
        return self._cron.stream()

    async def close(self) -> None:
        """Stop the schedule; no further ``RunRequest`` is emitted. Idempotent."""
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

    def _next_parameters(self) -> dict[str, Any]:
        """Return the run parameters for the fire now being emitted.

        Called once per emitted ``RunRequest`` by the delegate, so the counter
        advances only for fires that actually reach a consumer.

        Returns:
            A mapping carrying the 1-based ``fire_ordinal`` of this fire.
        """
        self._fired += 1
        return {"fire_ordinal": self._fired}
