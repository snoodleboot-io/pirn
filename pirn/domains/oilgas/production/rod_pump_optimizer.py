"""``RodPumpOptimizer`` — optimize rod pump stroke length and speed for sucker-rod lifted wells.

Algorithm:
    1. Receive a dynagraph card dict, ``target_fillage_pct``, and ``max_spm``.
    2. Validate all inputs are in expected ranges.
    3. Compute recommended SPM scaled by the fillage ratio.
    4. Return recommended SPM, stroke length, and fillage percentage.

Math:
    Recommended strokes per minute:

    $$\\text{SPM}^* = \\min\\!\\left(\\text{SPM}_{\\text{current}} \\times \\frac{F_{\\text{target}}}{100},\\; \\text{SPM}_{\\max}\\right)$$

    where :math:`F_{\\text{target}}` is the target fillage percentage and
    :math:`\\text{SPM}_{\\max}` is the maximum allowable strokes per minute.

    Pump fillage ratio (Drillinginfo convention):

    $$F = \\frac{q_{\\text{actual}}}{q_{\\text{theoretical}}} \\times 100\\%$$

References:
    - API RP 11L (4th ed., 1988) — Recommended Practice for Design
      Calculations for Sucker Rod Pumping Systems.
    - Gibbs, S.G. (1963). Predicting the behaviour of sucker-rod pumping
      systems. *JPT*, 15(7), 769-778. SPE-588-PA.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot


class RodPumpOptimizer(Knot):
    """Recommend stroke length and SPM settings based on dynagraph card analysis."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    async def process(
        self,
        dynagraph_card: dict[str, Any],
        target_fillage_pct: float,
        max_spm: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Analyse dynagraph card and recommend optimised SPM and stroke length.

        Args:
            dynagraph_card: Dict with ``surface_load_lbf`` (list[float]),
                ``surface_position_in`` (list[float]), ``current_spm``,
                and ``stroke_length_in``.
            target_fillage_pct: Target pump fillage percentage in (0, 100].
            max_spm: Positive maximum allowable strokes per minute.

        Returns:
            Dict with ``recommended_spm`` (float), ``recommended_stroke_in`` (float),
            and ``fillage_pct`` (float).
        """
        if not isinstance(target_fillage_pct, (int, float)):
            raise TypeError("RodPumpOptimizer: target_fillage_pct must be numeric")
        if not (0 < target_fillage_pct <= 100):
            raise ValueError("RodPumpOptimizer: target_fillage_pct must be in (0, 100]")
        if not isinstance(max_spm, (int, float)):
            raise TypeError("RodPumpOptimizer: max_spm must be numeric")
        if max_spm <= 0:
            raise ValueError("RodPumpOptimizer: max_spm must be positive")
        if not isinstance(dynagraph_card, dict):
            raise TypeError("RodPumpOptimizer: dynagraph_card must be a dict")
        current_spm = float(dynagraph_card.get("current_spm", max_spm))
        stroke_length_in = float(dynagraph_card.get("stroke_length_in", 144.0))
        recommended_spm = min(current_spm * (target_fillage_pct / 100.0), max_spm)
        return {
            "recommended_spm": recommended_spm,
            "recommended_stroke_in": stroke_length_in,
            "fillage_pct": target_fillage_pct,
        }
