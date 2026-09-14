"""Determinism, record/replay & time-travel debug (F29).

Makes agent runs reproducible and debuggable by recording and replaying every
non-deterministic I/O, leveraging the content-addressed DAG. The subpackage
layers five capabilities, each provider-neutral and backend-free at import time:

* **Record/replay** (S1) — core's own: every run records one lineage row and
  one content-addressed value per knot, and ``Tapestry.run(replay=ReplaySession)``
  serves them back without executing (PIR-872 deleted the cassette adapter that
  wrapped this). A recording that cannot be honoured raises core's
  ``ReplayError`` instead of silently calling out.
* **Deterministic mode** (S2) — a seed + a frozen-clock hook threaded through a
  run (:class:`~pirn_agents.determinism.determinism_context.DeterminismContext`)
  so time and randomness are reproducible; nothing calls the wall clock or the
  global RNG directly.
* **Trajectory capture** (S3) — a versioned, append-only structured trace of a
  run (:class:`~pirn_agents.determinism.run_trace.RunTrace`) built by a
  :class:`~pirn_agents.determinism.trajectory_emitter.TrajectoryEmitter`
  attached to a ``Tapestry``, which sees every knot's lineage automatically
  through ``on_lineage`` — no manual ``.record(...)`` call site to miss.
* **Time-travel** (S4) — step through a recorded trace
  (:class:`~pirn_agents.determinism.trace_inspector.TraceInspector`) and diff two
  runs (:class:`~pirn_agents.determinism.trace_differ.TraceDiffer`).
* **Snapshot/fork** (S5) — fork a new run from any F14 checkpoint
  (:class:`~pirn_agents.determinism.checkpoint_forker.CheckpointForker`).

``RunEval.run`` records one knot per eval item, so a whole suite replays
deterministically through the same core seam (``replay=``).
"""

from __future__ import annotations

__all__: list[str] = []
