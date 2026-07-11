"""``BenchmarkSample`` — one named benchmark measurement (a bag of numeric metrics)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

_LEADING_NUMBER = re.compile(r"[-+]?\d*\.?\d+")


@dataclass(frozen=True)
class BenchmarkSample(PirnOpaqueValue):
    """A single benchmark case's name and its measured metrics.

    Attributes
    ----------
    name:
        The benchmark case identifier (e.g. ``"ParallelToolExecutor"``).
    metrics:
        Mapping of metric key to numeric value (e.g. ``{"wall": 0.06,
        "speedup": 7.5}``). Units are stripped at parse time so values stay
        comparable across reports.
    """

    name: str
    metrics: Mapping[str, float]

    @classmethod
    def parse_line(cls, line: str) -> BenchmarkSample | None:
        """Parse one ``[benchmark] <name> k=v ...`` line, or return ``None``.

        This is the exact format F1/F2 micro-benchmarks print (e.g.
        ``[benchmark] ParallelToolExecutor N=8 wall=0.06s speedup=7.5x``). The
        leading numeric portion of each ``k=v`` value is taken, so unit suffixes
        (``s``, ``x``, ``calls/s``) are ignored. A line without the marker or
        with no numeric metrics yields ``None``.

        Args:
            line: A single line of benchmark output.

        Returns:
            A :class:`BenchmarkSample`, or ``None`` if the line is not a
            benchmark line or carries no parseable metric.
        """
        stripped = line.strip()
        if not stripped.startswith("[benchmark]"):
            return None
        body = stripped[len("[benchmark]") :].strip()
        tokens = body.split()
        if not tokens:
            return None
        name = tokens[0]
        metrics: dict[str, float] = {}
        for token in tokens[1:]:
            if "=" not in token:
                continue
            key, raw = token.split("=", 1)
            match = _LEADING_NUMBER.match(raw)
            if match is None:
                continue
            metrics[key] = float(match.group())
        if not metrics:
            return None
        return cls(name=name, metrics=metrics)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"name": self.name, "metrics": dict(self.metrics)}
