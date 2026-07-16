"""``RubricScore`` — the weighted result of rubric-mode judging."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class RubricScore(PirnOpaqueValue):
    """A rubric evaluation's weighted overall score plus per-criterion scores.

    Attributes
    ----------
    overall:
        The weight-averaged score across all criteria, in ``[0.0, 1.0]``.
    per_criterion:
        Mapping of criterion name to its ``[0.0, 1.0]`` score.
    detail:
        Free-form breakdown (e.g. raw self-consistency samples per criterion).
    """

    overall: float
    per_criterion: Mapping[str, float] = field(default_factory=dict)
    detail: Mapping[str, Any] = field(default_factory=dict)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "per_criterion": dict(self.per_criterion),
            "detail": dict(self.detail),
        }
