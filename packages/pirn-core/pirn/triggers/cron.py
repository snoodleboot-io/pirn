"""Cron-style trigger.

Fires a ``RunRequest`` at fixed intervals or at specific times.  Pure
Python; no external scheduling library required.

Three construction modes:

* ``CronTrigger(every_seconds=300)`` — every N seconds (most common
  for periodic jobs).
* ``CronTrigger(at_times=[...])`` — at specific ``datetime.time``
  values within each day (e.g., daily reports at 09:00 and 17:00).
* ``CronTrigger(delay_fn=...)`` — an arbitrary per-fire schedule,
  supplied as ``Callable[[int], float]`` mapping the next 1-based fire
  ordinal to the seconds to wait before it.

For full crontab-style expressions ("every Monday at 02:30 except
holidays"), wire in ``croniter`` or ``apscheduler`` behind ``delay_fn``
— a "seconds until the next cron instant" function drops straight in
without this module importing any scheduler.

The async sleep is injectable via ``sleep=`` so callers and tests can
advance the schedule deterministically with no wall-clock wait.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, time, timedelta
from typing import Any

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger


class CronTrigger(Trigger):
    """Time-based trigger that fires on a fixed interval, at times of day, or on a
    caller-supplied schedule.

    Three construction modes are supported:

    * **Interval mode** — ``CronTrigger(every_seconds=300)`` yields a
      ``RunRequest`` immediately on first iteration, then once every
      *N* seconds.
    * **At-times mode** — ``CronTrigger(at_times=[time(9, 0), time(17, 0)])``
      waits until the next matching wall-clock time (UTC) and yields then,
      repeating daily.
    * **Schedule-function mode** — ``CronTrigger(delay_fn=fn)`` waits
      ``fn(ordinal)`` seconds before each fire, where ``ordinal`` is the
      1-based index of the fire about to be emitted.

    For full crontab expressions, wrap ``croniter`` or ``apscheduler``
    behind ``delay_fn``.
    """

    def __init__(
        self,
        *,
        every_seconds: float | None = None,
        at_times: list[time] | None = None,
        delay_fn: Callable[[int], float] | None = None,
        parameters_factory: Callable[[], dict[str, Any]] | None = None,
        max_runs: int | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """Initialise the trigger.

        Args:
            every_seconds: Interval between runs in seconds (interval
                mode).  Mutually exclusive with ``at_times`` and
                ``delay_fn``.
            at_times: List of UTC ``datetime.time`` values at which to
                fire each day (at-times mode).  Mutually exclusive with
                ``every_seconds`` and ``delay_fn``.
            delay_fn: Maps the next 1-based fire ordinal to the seconds to
                wait before it (schedule-function mode) — the seam an
                external cron backend fills.  Mutually exclusive with
                ``every_seconds`` and ``at_times``.
            parameters_factory: Zero-argument callable returning a
                ``dict`` of run parameters.  Called once per emitted
                ``RunRequest``.  Defaults to an empty dict when ``None``.
            max_runs: Stop after this many ``RunRequest``s.  Runs
                indefinitely when ``None``.
            sleep: Async sleep awaited between fires; injected in tests
                and by callers driving a virtual clock.  Defaults to
                :func:`asyncio.sleep`, resolved at call time so existing
                module-level monkeypatching keeps working.

        Raises:
            TypeError: If none, or more than one, of ``every_seconds``,
                ``at_times`` and ``delay_fn`` are supplied.
            ValueError: If ``max_runs`` is supplied but is not an ``int``
                greater than or equal to 1.
        """
        modes = (every_seconds is not None, at_times is not None, delay_fn is not None)
        if not any(modes):
            raise TypeError("CronTrigger requires one of every_seconds=, at_times= or delay_fn=")
        if sum(modes) > 1:
            raise TypeError(
                "CronTrigger: pass exactly one of every_seconds=, at_times= or delay_fn=, not both"
            )
        if max_runs is not None and (isinstance(max_runs, bool) or not isinstance(max_runs, int)):
            raise ValueError(f"CronTrigger: max_runs must be an int >= 1, got {max_runs!r}")
        if max_runs is not None and max_runs < 1:
            raise ValueError(f"CronTrigger: max_runs must be an int >= 1, got {max_runs!r}")

        self._every_seconds = every_seconds
        self._at_times = sorted(at_times or [])
        self._delay_fn = delay_fn
        self._parameters_factory = parameters_factory
        self._max_runs = max_runs
        self._sleep = sleep
        self._closed = False

    @property
    def name(self) -> str:
        return "CronTrigger"

    async def stream(self) -> AsyncIterator[RunRequest]:
        """Yield ``RunRequest`` objects according to the configured schedule.

        In interval mode the first request is yielded immediately; in
        at-times and schedule-function modes the generator waits the
        scheduled delay before yielding.  Stops after ``max_runs``
        requests when set, or when ``close()`` is called — in neither
        case does it sleep past the final fire.

        Yields:
            One ``RunRequest`` per scheduled fire time.
        """
        emitted = 0
        while not self._closed:
            if self._max_runs is not None and emitted >= self._max_runs:
                return
            delay = self._delay_before(emitted + 1)
            # Interval mode's first fire is immediate (delay 0) and must not
            # await at all.  Every later fire awaits even a zero delay, so the
            # loop stays cooperative when the schedule collapses to no wait.
            if emitted > 0 or delay > 0:
                await self._wait(delay)
                if self._closed:
                    return
            yield self._build_request()
            emitted += 1

    def _delay_before(self, ordinal: int) -> float:
        """Seconds to wait before emitting the ``ordinal``-th (1-based) request.

        Args:
            ordinal: 1-based index of the fire about to be emitted.

        Returns:
            The delay in seconds, per the configured construction mode.
            Interval mode returns ``0.0`` for the first fire so it lands
            immediately, then the configured interval.
        """
        if self._delay_fn is not None:
            return self._delay_fn(ordinal)
        if self._every_seconds is not None:
            return 0.0 if ordinal == 1 else self._every_seconds
        return self._seconds_until_next_at_time()

    async def _wait(self, delay: float) -> None:
        """Await the configured sleep for ``delay`` seconds.

        Resolves :func:`asyncio.sleep` at call time rather than binding it
        in ``__init__`` so that module-level monkeypatching of
        ``pirn.triggers.cron.asyncio.sleep`` continues to work.

        Args:
            delay: Seconds to wait.
        """
        if self._sleep is not None:
            await self._sleep(delay)
        else:
            await asyncio.sleep(delay)

    def _build_request(self) -> RunRequest:
        """Construct a ``RunRequest`` using the configured parameters factory.

        Returns:
            A new ``RunRequest`` whose ``parameters`` dict is produced by
            ``parameters_factory()``, or an empty dict if no factory was
            configured.
        """
        params: dict[str, Any] = (
            self._parameters_factory() if self._parameters_factory is not None else {}
        )
        return RunRequest(parameters=params)

    def _seconds_until_next_at_time(self) -> float:
        """Return the number of seconds until the next scheduled at-time fires.

        Considers all configured times for today (UTC); if all have
        passed, returns the wait until the first time tomorrow.

        Returns:
            Seconds to sleep before the next fire time.
        """
        now = datetime.now(UTC)
        today = now.date()
        for t in self._at_times:
            candidate = datetime.combine(today, t, tzinfo=UTC)
            if candidate > now:
                return (candidate - now).total_seconds()
        # All today's times have passed; first time tomorrow.
        tomorrow = today + timedelta(days=1)
        candidate = datetime.combine(tomorrow, self._at_times[0], tzinfo=UTC)
        return (candidate - now).total_seconds()

    async def close(self) -> None:
        """Signal the trigger to stop after the current sleep completes."""
        self._closed = True
