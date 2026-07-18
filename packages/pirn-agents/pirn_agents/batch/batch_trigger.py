"""``BatchTrigger`` — the interface that fires a batch run (F28-S5 / PIR-584).

A trigger is a provider-neutral source of *fire* signals: an async stream of
monotonically increasing fire ordinals, one per time a bound batch should run.
:class:`~pirn_agents.batch.interval_trigger.IntervalTrigger` fires on a schedule
(constant interval, or an injected ``delay_fn`` — the seam a cron backend plugs
into) and :class:`~pirn_agents.batch.event_trigger.EventTrigger` fires on demand.
:class:`~pirn_agents.batch.triggered_batch.TriggeredBatch` consumes the stream and
runs a :class:`~pirn_agents.batch.map_agent.MapAgent` once per fire.

Triggers are runtime objects (like ``MapAgent``), not lineage values, so they are
plain classes with injectable clocks/sleeps for deterministic tests — no wall
clock, no real scheduler, no backend import on this path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator


class BatchTrigger:
    """Interface yielding an async stream of batch-run fire ordinals."""

    def fires(self) -> AsyncIterator[int]:
        """Return an async iterator yielding a 1-based ordinal per fire.

        Raises:
            NotImplementedError: Always, in the base; every concrete trigger
                overrides this with its own async-generator implementation.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement fires()")
