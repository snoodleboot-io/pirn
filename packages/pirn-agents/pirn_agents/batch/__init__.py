"""F28 — batch / fleet execution engine.

High-throughput execution of *many* agent runs: :class:`~pirn_agents.batch.map_agent.MapAgent`
maps a per-item agent callable over a dataset with per-item isolation (one
item's failure never sinks the batch), bounded in-flight concurrency +
backpressure, optional F21 rate-aware adaptive scheduling, F14-backed resumable
checkpointing, a streaming result sink with a progress/partial-failure report,
and optional cron/event triggers.

This subpackage is imported explicitly (``pirn_agents.batch.<module>``) rather
than re-exported through :mod:`pirn_agents` — mirroring the ``sessions`` and
``resilience`` subpackages — so a bare ``import pirn_agents`` stays free of any
batch machinery. Every optional backend (e.g. the cron trigger) is imported
lazily through :func:`pirn_agents._require._require`, keeping the import path
backend-free.
"""

from __future__ import annotations
