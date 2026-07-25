"""``BenchmarkDelta`` — diff a current :class:`BenchmarkReport` against a baseline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.benchmarks.benchmark_report import BenchmarkReport


@dataclass(frozen=True)
class BenchmarkDelta(PirnOpaqueValue):
    """Per-metric comparison of a ``current`` run against a ``baseline`` run.

    Emits both a machine-readable JSON form (for CI to store/track) and a
    compact Markdown table (for a PR comment). Every ``(sample, metric)`` pair
    present in either report yields a row carrying the baseline value, the
    current value, the absolute delta, and the percentage change — so a
    reviewer sees at a glance what moved.

    Attributes
    ----------
    baseline:
        The stored reference report.
    current:
        The freshly measured report.
    """

    baseline: BenchmarkReport
    current: BenchmarkReport

    def rows(self) -> list[dict[str, Any]]:
        """Return one comparison row per ``(sample, metric)`` seen in either report.

        Rows are sorted by ``(name, metric)`` for stable output. ``baseline`` or
        ``current`` is ``None`` in a row when that side lacks the metric (a
        metric added or removed between runs); ``delta``/``pct`` are then
        ``None`` too.
        """
        keys: set[tuple[str, str]] = set()
        for report in (self.baseline, self.current):
            for sample in report.samples:
                for metric_key in sample.metrics:
                    keys.add((sample.name, metric_key))

        rows: list[dict[str, Any]] = []
        for name, metric_key in sorted(keys):
            base = self.baseline.metric(name, metric_key)
            curr = self.current.metric(name, metric_key)
            delta: float | None = None
            pct: float | None = None
            if base is not None and curr is not None:
                delta = curr - base
                pct = (delta / base * 100.0) if base != 0 else None
            rows.append(
                {
                    "name": name,
                    "metric": metric_key,
                    "baseline": base,
                    "current": curr,
                    "delta": delta,
                    "pct": pct,
                }
            )
        return rows

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise the delta rows to a machine-readable JSON string."""
        return json.dumps({"rows": self.rows()}, indent=indent, sort_keys=True)

    def to_markdown(self) -> str:
        """Render the delta as a Markdown table suitable for a PR comment."""
        header = (
            "| benchmark | metric | baseline | current | delta | % |\n"
            "| --- | --- | ---: | ---: | ---: | ---: |"
        )
        lines = [header]
        for row in self.rows():
            lines.append(
                f"| {row['name']} | {row['metric']} | "
                f"{self._fmt(row['baseline'])} | {self._fmt(row['current'])} | "
                f"{self._fmt(row['delta'])} | {self._fmt_pct(row['pct'])} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _fmt(value: float | None) -> str:
        return "—" if value is None else f"{value:.4g}"

    @staticmethod
    def _fmt_pct(value: float | None) -> str:
        return "—" if value is None else f"{value:+.1f}%"

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"rows": self.rows()}
