"""Determinism, record/replay & time-travel debug (F29).

Makes agent runs reproducible and debuggable by recording and replaying every
non-deterministic I/O, leveraging the content-addressed DAG. The subpackage
layers five capabilities, each provider-neutral and backend-free at import time:

* **Cassettes** (S1) — record every LLM/tool/retrieval I/O keyed by a content
  digest and replay it deterministically offline
  (:class:`~pirn_agents.determinism.cassette_recorder.CassetteRecorder` over a
  serialisable :class:`~pirn_agents.determinism.cassette.Cassette`, with
  ``record`` / ``replay`` / ``passthrough`` modes). A missing replay entry raises
  :class:`~pirn_agents.exceptions.missing_cassette_entry_error.MissingCassetteEntryError`
  instead of silently calling out.
* **Deterministic mode** (S2) — a seed + a frozen-clock hook threaded through a
  run (:class:`~pirn_agents.determinism.determinism_context.DeterminismContext`)
  so time and randomness are reproducible; nothing calls the wall clock or the
  global RNG directly.
* **Trajectory capture** (S3) — a versioned, append-only structured trace of a
  run (:class:`~pirn_agents.determinism.run_trace.RunTrace`) built cheaply by a
  :class:`~pirn_agents.determinism.trajectory_recorder.TrajectoryRecorder`.
* **Time-travel** (S4) — step through a recorded trace
  (:class:`~pirn_agents.determinism.trace_inspector.TraceInspector`) and diff two
  runs (:class:`~pirn_agents.determinism.trace_differ.TraceDiffer`).
* **Snapshot/fork** (S5) — fork a new run from any F14 checkpoint
  (:class:`~pirn_agents.determinism.checkpoint_forker.CheckpointForker`).

The concrete cassette recorder also backs F12's ``RunRecorder`` seam via
:class:`~pirn_agents.evaluation.cassette_run_recorder.CassetteRunRecorder`, so
``run_eval`` can replay a whole suite deterministically. Cassette persistence
defaults to the in-process
:class:`~pirn_agents.determinism.in_memory_cassette_store.InMemoryCassetteStore`
or the stdlib-JSON
:class:`~pirn_agents.determinism.file_cassette_store.FileCassetteStore`; no heavy
backend is required.
"""

from __future__ import annotations

__all__: list[str] = []
