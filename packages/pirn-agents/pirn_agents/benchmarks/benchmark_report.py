"""``BenchmarkReport`` — a JSON-serialisable collection of :class:`BenchmarkSample`\\ s."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.benchmarks.benchmark_sample import BenchmarkSample


@dataclass(frozen=True)
class BenchmarkReport(PirnOpaqueValue):
    """One benchmark run's samples, round-trippable to and from JSON.

    The machine-readable artifact CI stores and PRs diff. Build one by parsing
    captured benchmark output (:meth:`from_output`) or from stored JSON
    (:meth:`from_json`); serialise via :meth:`to_json`.

    Attributes
    ----------
    samples:
        The parsed benchmark cases, in first-seen order.
    """

    samples: tuple[BenchmarkSample, ...] = ()

    @classmethod
    def from_output(cls, text: str) -> BenchmarkReport:
        """Build a report from raw benchmark stdout by parsing every marker line.

        Non-benchmark lines are ignored, so the full captured pytest output can
        be passed directly.
        """
        samples = [
            sample
            for line in text.splitlines()
            if (sample := BenchmarkSample.parse_line(line)) is not None
        ]
        return cls(samples=tuple(samples))

    @classmethod
    def from_json(cls, data: str) -> BenchmarkReport:
        """Reconstruct a report from its :meth:`to_json` form."""
        payload = json.loads(data)
        samples = tuple(
            BenchmarkSample(name=item["name"], metrics=dict(item["metrics"]))
            for item in payload.get("samples", [])
        )
        return cls(samples=samples)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise the report to a stable, machine-readable JSON string."""
        payload = {"samples": [{"name": s.name, "metrics": dict(s.metrics)} for s in self.samples]}
        return json.dumps(payload, indent=indent, sort_keys=True)

    def metric(self, name: str, key: str) -> float | None:
        """Return metric ``key`` of sample ``name``, or ``None`` if absent."""
        for sample in self.samples:
            if sample.name == name:
                return sample.metrics.get(key)
        return None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"samples": [{"name": s.name, "metrics": dict(s.metrics)} for s in self.samples]}
