"""``EvalReport`` — aggregated quality report over an eval run."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.evaluation.eval_case_result import EvalCaseResult


@dataclass(frozen=True)
class EvalReport(PirnOpaqueValue):
    """The per-item results and metric aggregates of one eval run.

    Aligns with the F10 benchmark report shape (a JSON document of named cases
    carrying numeric metrics) so eval quality and perf artifacts diff the same
    way in CI. :meth:`aggregate` gives the mean of each metric across cases — the
    values a regression gate checks against thresholds.

    Attributes
    ----------
    results:
        Per-item :class:`EvalCaseResult`\\ s, in run order.
    """

    results: tuple[EvalCaseResult, ...] = ()

    def __post_init__(self) -> None:
        """Validate and normalise ``results`` to a tuple.

        Raises:
            TypeError: If ``results`` is not a sequence of
                :class:`EvalCaseResult`.
        """
        if isinstance(self.results, (str, bytes)) or not isinstance(self.results, Sequence):
            raise TypeError(
                f"EvalReport.results must be a sequence of EvalCaseResult, "
                f"got {type(self.results).__name__}"
            )
        results = tuple(self.results)
        for index, result in enumerate(results):
            if not isinstance(result, EvalCaseResult):
                raise TypeError(
                    f"EvalReport.results[{index}] must be an EvalCaseResult, "
                    f"got {type(result).__name__}"
                )
        object.__setattr__(self, "results", results)

    def aggregate(self) -> dict[str, float]:
        """Return the mean of each metric across all cases that report it."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for result in self.results:
            for name, score in result.metrics.items():
                totals[name] = totals.get(name, 0.0) + score
                counts[name] = counts.get(name, 0) + 1
        return {name: totals[name] / counts[name] for name in totals}

    def metric(self, name: str) -> float | None:
        """Return the mean of metric ``name`` across cases, or ``None`` if absent."""
        return self.aggregate().get(name)

    @property
    def passed(self) -> bool:
        """Whether every case with a verdict passed (vacuously ``True`` if none)."""
        return all(r.passed for r in self.results if r.passed is not None)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise the report (results + aggregate) to a stable JSON string."""
        payload = {
            "results": [r._pirn_audit_dict() for r in self.results],
            "aggregate": self.aggregate(),
        }
        return json.dumps(payload, indent=indent, sort_keys=True)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"results": [r._pirn_audit_dict() for r in self.results]}
