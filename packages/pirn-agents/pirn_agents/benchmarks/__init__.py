"""Machine-readable benchmark report + delta emitter for the perf harness.

The measurement half of F10. The ``@pytest.mark.benchmark`` suite prints
``[benchmark] <name> key=value ...`` lines (the format F1/F2 micro-benchmarks
already emit); :class:`~pirn_agents.benchmarks.benchmark_sample.BenchmarkSample`
parses one such line and
:class:`~pirn_agents.benchmarks.benchmark_report.BenchmarkReport` collects a run
into a JSON-serialisable document.
:class:`~pirn_agents.benchmarks.benchmark_delta.BenchmarkDelta` diffs a report
against a stored baseline so a PR can surface per-metric deltas.
"""

__all__: list[str] = []
