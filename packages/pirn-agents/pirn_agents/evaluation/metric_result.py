"""``MetricResult`` — one metric's score plus explanatory detail."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class MetricResult(PirnOpaqueValue):
    """A single metric's name, numeric score, and explanatory detail.

    The uniform value every evaluation metric returns, so a runner can collect
    heterogeneous metrics into one report. ``score`` is conventionally in
    ``[0.0, 1.0]`` (1.0 = best) but the type does not enforce a range so a
    metric may report a raw magnitude when that is more meaningful.

    Attributes
    ----------
    name:
        Metric identifier (e.g. ``"exact_match"``, ``"faithfulness"``).
    score:
        The numeric score, conventionally in ``[0.0, 1.0]``.
    detail:
        Free-form, JSON-serialisable breakdown of how the score was reached
        (component counts, thresholds, per-item verdicts).
    """

    name: str
    score: float
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the name and coerce the score to a float.

        Raises:
            TypeError: If ``name`` is not a str or ``score`` is not a real
                number (``bool`` is rejected explicitly, since ``True`` would
                otherwise coerce to ``1.0``).
        """
        if not isinstance(self.name, str):
            raise TypeError(f"MetricResult.name must be a str, got {type(self.name).__name__}")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise TypeError(
                f"MetricResult.score must be a real number, got {type(self.score).__name__}"
            )
        object.__setattr__(self, "score", float(self.score))

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"name": self.name, "score": self.score, "detail": dict(self.detail)}
