"""Emitters — what observes a run.

An ``Emitter`` receives status events, lineage records, and run
results as they happen; emitters fan run state out to logs, metrics
systems, message buses, and traces.

Multiple emitters can be subscribed to a tapestry; each receives
every event.  A single emitter can be subscribed to multiple
tapestries.

The ``Emitter`` base class is intentionally narrow: ``on_status``,
``on_knot_result``, ``on_lineage``, ``on_run_result`` and ``close``, each a
no-op by default.  Implementations subclass it and override the ones they
care about.
"""
