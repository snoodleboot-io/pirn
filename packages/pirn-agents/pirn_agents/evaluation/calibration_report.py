"""``CalibrationReport`` — judge-vs-gold agreement and error summary."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class CalibrationReport(PirnOpaqueValue):
    """How closely an :class:`EvaluationJudge` tracks a human gold set.

    Attributes
    ----------
    agreement:
        Fraction of gold items whose judged overall fell within the tolerance of
        the expected score, in ``[0, 1]`` (1.0 = perfectly calibrated).
    mean_abs_error:
        Mean absolute difference between judged and expected overall scores.
    n:
        Number of gold items evaluated.
    detail:
        Per-item judged/expected/error records for inspection.
    """

    agreement: float
    mean_abs_error: float
    n: int
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise the report to a stable, machine-readable JSON string."""
        return json.dumps(
            {
                "agreement": self.agreement,
                "mean_abs_error": self.mean_abs_error,
                "n": self.n,
                "detail": dict(self.detail),
            },
            indent=indent,
            sort_keys=True,
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "agreement": self.agreement,
            "mean_abs_error": self.mean_abs_error,
            "n": self.n,
            "detail": dict(self.detail),
        }
