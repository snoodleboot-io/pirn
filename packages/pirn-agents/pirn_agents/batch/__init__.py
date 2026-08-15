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
"""

from __future__ import annotations
