"""Reusable ``@pytest.mark.benchmark`` fixtures for the perf harness (PIR-315).

Provides a :class:`BenchmarkRecorder` fixture every benchmark case uses to
capture measurements uniformly. The recorder prints one ``[benchmark] <name>
k=v ...`` line per sample at teardown — the exact format F1/F2 benchmarks emit
and that :class:`~pirn_agents.benchmarks.benchmark_report.BenchmarkReport`
parses — and exposes the samples as a report for in-test assertions. Timing is
measured with :func:`time.perf_counter`; the harness never depends on the
pytest-benchmark plugin.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import pytest

from pirn_agents.benchmarks.benchmark_report import BenchmarkReport
from pirn_agents.benchmarks.benchmark_sample import BenchmarkSample


class BenchmarkRecorder:
    """Collects named benchmark samples and renders them in the shared format."""

    def __init__(self) -> None:
        self._samples: list[BenchmarkSample] = []

    def record(self, name: str, **metrics: float) -> None:
        """Record one benchmark case's metrics under ``name``."""
        self._samples.append(BenchmarkSample(name=name, metrics=dict(metrics)))

    @staticmethod
    def time_block() -> Callable[[], float]:  # pragma: no cover - trivial helper
        """Return a stopwatch closure; call it to read elapsed seconds."""
        start = time.perf_counter()
        return lambda: time.perf_counter() - start

    def report(self) -> BenchmarkReport:
        """Return the recorded samples as a :class:`BenchmarkReport`."""
        return BenchmarkReport(samples=tuple(self._samples))

    def render_lines(self) -> list[str]:
        """Render each sample as a ``[benchmark] name k=v ...`` line."""
        lines: list[str] = []
        for sample in self._samples:
            metrics = " ".join(f"{k}={v:.6g}" for k, v in sample.metrics.items())
            lines.append(f"[benchmark] {sample.name} {metrics}".rstrip())
        return lines


@pytest.fixture
def benchmark_recorder() -> Iterator[BenchmarkRecorder]:
    """Yield a :class:`BenchmarkRecorder`, printing its samples at teardown."""
    recorder = BenchmarkRecorder()
    yield recorder
    for line in recorder.render_lines():
        print(line)
