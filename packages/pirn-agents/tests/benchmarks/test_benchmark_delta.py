"""Mirrored tests for the :class:`BenchmarkDelta` emitter (PIR-323)."""

from __future__ import annotations

import json

from pirn_agents.benchmarks.benchmark_delta import BenchmarkDelta
from pirn_agents.benchmarks.benchmark_report import BenchmarkReport
from pirn_agents.benchmarks.benchmark_sample import BenchmarkSample


def _report(name: str, **metrics: float) -> BenchmarkReport:
    return BenchmarkReport(samples=(BenchmarkSample(name=name, metrics=metrics),))


class TestRows:
    def test_delta_and_pct_computed(self) -> None:
        baseline = _report("Exec", wall=0.10)
        current = _report("Exec", wall=0.12)
        rows = BenchmarkDelta(baseline, current).rows()
        assert len(rows) == 1
        row = rows[0]
        assert row["baseline"] == 0.10
        assert row["current"] == 0.12
        assert abs(row["delta"] - 0.02) < 1e-9
        assert abs(row["pct"] - 20.0) < 1e-9

    def test_metric_only_in_current_has_none_baseline(self) -> None:
        baseline = _report("Exec", wall=0.10)
        current = BenchmarkReport(
            samples=(BenchmarkSample(name="Exec", metrics={"wall": 0.10, "tokens": 42}),)
        )
        rows = {r["metric"]: r for r in BenchmarkDelta(baseline, current).rows()}
        assert rows["tokens"]["baseline"] is None
        assert rows["tokens"]["delta"] is None

    def test_zero_baseline_pct_is_none(self) -> None:
        rows = BenchmarkDelta(_report("c", x=0.0), _report("c", x=5.0)).rows()
        assert rows[0]["pct"] is None

    def test_rows_sorted_stable(self) -> None:
        base = BenchmarkReport(samples=(BenchmarkSample(name="b", metrics={"z": 1, "a": 1}),))
        rows = BenchmarkDelta(base, base).rows()
        assert [r["metric"] for r in rows] == ["a", "z"]


class TestRendering:
    def test_to_json_is_machine_readable(self) -> None:
        delta = BenchmarkDelta(_report("Exec", wall=0.10), _report("Exec", wall=0.11))
        payload = json.loads(delta.to_json())
        assert payload["rows"][0]["name"] == "Exec"

    def test_to_markdown_has_table_header_and_row(self) -> None:
        delta = BenchmarkDelta(_report("Exec", wall=0.10), _report("Exec", wall=0.11))
        md = delta.to_markdown()
        assert "| benchmark | metric | baseline | current | delta | % |" in md
        assert "Exec" in md
        assert "%" in md
