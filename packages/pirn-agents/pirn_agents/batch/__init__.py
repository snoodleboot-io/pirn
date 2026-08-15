"""F28 — batch / fleet execution engine.

High-throughput execution of *many* agent runs: :class:`~pirn_agents.batch.map_agent.MapAgent`
maps a per-item agent callable over a dataset with per-item isolation (one
item's failure never sinks the batch), bounded in-flight concurrency +
backpressure, optional F21 rate-aware adaptive scheduling, F14-backed resumable
checkpointing, a streaming result sink with a progress/partial-failure report,
and optional schedule/event triggers.

This subpackage is imported explicitly (``pirn_agents.batch.<module>``) rather
than re-exported through :mod:`pirn_agents` — mirroring the ``sessions`` and
``resilience`` subpackages — so a bare ``import pirn_agents`` stays free of any
batch machinery.

Triggering is core's, not this package's.
:class:`~pirn_agents.batch.triggered_batch.TriggeredBatch` accepts any
:class:`pirn.triggers.base.Trigger`, and the two triggers defined here —
:class:`~pirn_agents.batch.interval_trigger.IntervalTrigger` (schedule, backed by
:class:`pirn.triggers.cron.CronTrigger`) and
:class:`~pirn_agents.batch.event_trigger.EventTrigger` (in-process, on demand) —
are ``Trigger`` subclasses like any other. Consequently a broker- or HTTP-backed
batch needs no entry point here: construct core's ``KafkaTrigger``,
``ValKeyTrigger`` or ``WebhookTrigger`` and hand it to ``TriggeredBatch``. Those
backends' optional dependencies are declared and imported by ``pirn-core``, so
nothing on this import path pulls one in.

**Trigger ownership.** A trigger's lifecycle belongs to whoever constructed it.
``TriggeredBatch`` binds a trigger without consuming it and leaves it open, so
the same trigger can drive a later run; pass ``owns_trigger=True`` to hand it
over for the fire-and-forget shape, where a trigger constructed inline is closed
on every exit path exactly as :func:`pirn.triggers.base.run_forever` does. This
matters because ``close()`` is **terminal** for both triggers here: a closed
``IntervalTrigger`` emits nothing further, and a closed ``EventTrigger`` also
refuses ``fire()``, so nothing can ever feed its stream again. Closing a trigger
the caller still holds would therefore turn their next run into a silent no-op
or a deadlock, which is why ownership is explicit rather than assumed.

The two triggers differ in what survives a completed run. ``IntervalTrigger`` is
re-streamable: each ``stream()`` is independent, numbering its own fires from 1
with its own ``max_fires`` budget, so exhausting a schedule leaves the trigger
reusable and two concurrent consumers never share a counter. ``EventTrigger`` is
single-use: its queue is shared, so concurrent consumers split the signals
between them, and once closed it is spent. Either way a spent trigger raises on
``stream()`` rather than hanging or quietly reporting an empty run.
"""

from __future__ import annotations
