"""``RiskBasedInspectionScorer`` — score an asset for risk-based inspection."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RiskBasedInspectionScorer(Knot):
    """Compute an RBI risk score = probability_of_failure x consequence."""

    def __init__(
        self,
        *,
        corrosion_assessment: Knot,
        consequence_score: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(consequence_score, (int, float)):
            raise TypeError(
                "RiskBasedInspectionScorer: consequence_score must be numeric"
            )
        if not 0.0 <= consequence_score <= 1.0:
            raise ValueError(
                "RiskBasedInspectionScorer: consequence_score must lie in [0, 1]"
            )
        self._consequence_score = float(consequence_score)
        super().__init__(
            corrosion_assessment=corrosion_assessment, _config=_config, **kwargs
        )

    async def process(
        self,
        corrosion_assessment: dict[str, float],
        **_: Any,
    ) -> dict[str, float]:
        """Compute the RBI risk score as probability_of_failure x consequence from the corrosion assessment and return it.

        Args:
            corrosion_assessment: Dict of corrosion rates (e.g.
                ``max_rate_mpy``) from which the probability of failure is
                derived.

        Returns:
            Dict with ``probability_of_failure``, ``consequence``, and
            ``risk_score`` (product of the two).
        """
        max_rate = float(corrosion_assessment.get("max_rate_mpy", 0.0))
        pof = min(max_rate / 10.0, 1.0)
        return {
            "probability_of_failure": pof,
            "consequence": self._consequence_score,
            "risk_score": pof * self._consequence_score,
        }
