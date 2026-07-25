"""Unit tests for :class:`BenchmarkSample` line parsing."""

from __future__ import annotations

from pirn_agents.benchmarks.benchmark_sample import BenchmarkSample


class TestParseLine:
    def test_parses_f1_style_line(self) -> None:
        line = (
            "[benchmark] ParallelToolExecutor N=8 per_call=0.05s "
            "wall=0.0600s serial=0.4000s throughput=133.3 calls/s speedup=6.7x"
        )
        sample = BenchmarkSample.parse_line(line)
        assert sample is not None
        assert sample.name == "ParallelToolExecutor"
        assert sample.metrics["N"] == 8
        assert sample.metrics["wall"] == 0.06
        assert sample.metrics["speedup"] == 6.7
        # Unit suffixes stripped to bare numbers.
        assert sample.metrics["per_call"] == 0.05

    def test_non_benchmark_line_returns_none(self) -> None:
        assert BenchmarkSample.parse_line("just some log output") is None

    def test_marker_without_metrics_returns_none(self) -> None:
        assert BenchmarkSample.parse_line("[benchmark] NamedOnly") is None

    def test_negative_and_signed_values(self) -> None:
        sample = BenchmarkSample.parse_line("[benchmark] case delta=-1.5 gain=+2")
        assert sample is not None
        assert sample.metrics["delta"] == -1.5
        assert sample.metrics["gain"] == 2.0

    def test_leading_whitespace_tolerated(self) -> None:
        sample = BenchmarkSample.parse_line("   [benchmark] c x=1  ")
        assert sample is not None and sample.name == "c"
