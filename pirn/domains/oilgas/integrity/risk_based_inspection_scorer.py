"""``RiskBasedInspectionScorer`` — score an asset for risk-based inspection.

Algorithm:
    1. Receive a corrosion assessment dict and a ``consequence_score`` in [0, 1].
    2. Validate that ``consequence_score`` is numeric and in [0, 1].
    3. Derive probability-of-failure from the max corrosion rate.
    4. Compute risk score = probability_of_failure × consequence.
    5. Return a dict with all three values.

Math:
    Probability of failure (linearised approximation):

    $$\\text{PoF} = \\min\\!\\left(\\frac{r_{\\max}}{r_{\\text{ref}}},\\; 1\\right)$$

    Risk score (API RP 580 risk matrix):

    $$R = \\text{PoF} \\times C$$

    where :math:`r_{\\max}` is the maximum corrosion rate in mpy,
    :math:`r_{\\text{ref}} = 10` mpy is the reference rate, and :math:`C` is
    the consequence score in [0, 1].

References:
    - API RP 580 (3rd ed., 2016) — Risk-Based Inspection.
    - API RP 581 (3rd ed., 2016) — Risk-Based Inspection Methodology.
"""

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
        consequence_score: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            corrosion_assessment=corrosion_assessment,
            consequence_score=consequence_score,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        corrosion_assessment: dict[str, float],
        consequence_score: float,
        **_: Any,
    ) -> dict[str, float]:
        """Compute the RBI risk score from the corrosion assessment and consequence score and return it.

        Args:
            corrosion_assessment: Dict of corrosion rates (e.g.
                ``max_rate_mpy``) from which the probability of failure is
                derived.
            consequence_score: Numeric consequence score in [0, 1].

        Returns:
            Dict with ``probability_of_failure``, ``consequence``, and
            ``risk_score`` (product of the two).
        """
        if not isinstance(consequence_score, (int, float)):
            raise TypeError(
                "RiskBasedInspectionScorer: consequence_score must be numeric"
            )
        if not 0.0 <= consequence_score <= 1.0:
            raise ValueError(
                "RiskBasedInspectionScorer: consequence_score must lie in [0, 1]"
            )
        max_rate = float(corrosion_assessment.get("max_rate_mpy", 0.0))
        pof = min(max_rate / 10.0, 1.0)
        cscore = float(consequence_score)
        return {
            "probability_of_failure": pof,
            "consequence": cscore,
            "risk_score": pof * cscore,
        }
