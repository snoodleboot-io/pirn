"""Unit tests for :class:`BenchmarkReport` parsing and JSON round-trip."""

from __future__ import annotations

from pirn_agents.benchmarks.benchmark_report import BenchmarkReport

_CAPTURED = """
some pytest noise
[benchmark] ExecutorThroughput wall=0.06s speedup=6.7x
more noise
[benchmark] RetrievalTopK latency=0.002s recall=1.0
"""


class TestFromOutput:
    def test_parses_only_benchmark_lines(self) -> None:
        report = BenchmarkReport.from_output(_CAPTURED)
        assert len(report.samples) == 2
        assert report.metric("ExecutorThroughput", "speedup") == 6.7
        assert report.metric("RetrievalTopK", "recall") == 1.0

    def test_metric_absent_returns_none(self) -> None:
        report = BenchmarkReport.from_output(_CAPTURED)
        assert report.metric("Nope", "x") is None
        assert report.metric("ExecutorThroughput", "nope") is None


class TestJsonRoundTrip:
    def test_to_from_json_preserves_samples(self) -> None:
        report = BenchmarkReport.from_output(_CAPTURED)
        restored = BenchmarkReport.from_json(report.to_json())
        assert restored.metric("ExecutorThroughput", "wall") == 0.06
        assert restored.metric("RetrievalTopK", "latency") == 0.002

    def test_to_json_is_stable_sorted(self) -> None:
        report = BenchmarkReport.from_output(_CAPTURED)
        assert report.to_json() == report.to_json()

    def test_empty_report(self) -> None:
        assert BenchmarkReport().to_json()
        assert BenchmarkReport.from_output("no benchmarks here").samples == ()
