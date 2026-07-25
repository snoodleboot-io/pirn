"""``MetricThreshold`` — a minimum acceptable score for one metric."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class MetricThreshold(PirnOpaqueValue):
    """The minimum score a named metric must reach to pass.

    Higher-is-better semantics: a metric ``score`` passes when it is at least
    ``min_score``. (Lower-is-better metrics such as redundant-call rate are not
    given a floor threshold.)

    Attributes
    ----------
    metric:
        The metric name this threshold guards (e.g. ``"faithfulness"``).
    min_score:
        The inclusive minimum acceptable score.
    """

    metric: str
    min_score: float

    def __post_init__(self) -> None:
        """Validate the metric name and minimum score.

        Raises:
            TypeError: If ``metric`` is not a str or ``min_score`` is not a real
                number.
        """
        if not isinstance(self.metric, str):
            raise TypeError(
                f"MetricThreshold.metric must be a str, got {type(self.metric).__name__}"
            )
        if isinstance(self.min_score, bool) or not isinstance(self.min_score, (int, float)):
            raise TypeError(
                f"MetricThreshold.min_score must be a real number, "
                f"got {type(self.min_score).__name__}"
            )
        object.__setattr__(self, "min_score", float(self.min_score))

    def passes(self, score: float) -> bool:
        """Return whether ``score`` meets this threshold."""
        return score >= self.min_score

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"metric": self.metric, "min_score": self.min_score}
