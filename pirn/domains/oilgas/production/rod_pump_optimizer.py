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
from pirn.core.knot_config import KnotConfig


class RodPumpOptimizer(Knot):
    """Recommend stroke length and SPM settings based on dynagraph card analysis."""

    def __init__(
        self,
        *,
        dynagraph_card: Knot,
        target_fillage_pct: Knot | float,
        max_spm: Knot | float,
        spm_field: Knot | str = "current_spm",
        stroke_field: Knot | str = "stroke_length_in",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dynagraph_card=dynagraph_card,
            target_fillage_pct=target_fillage_pct,
            max_spm=max_spm,
            spm_field=spm_field,
            stroke_field=stroke_field,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dynagraph_card: dict[str, Any],
        target_fillage_pct: float,
        max_spm: float,
        spm_field: str = "current_spm",
        stroke_field: str = "stroke_length_in",
        **_: Any,
    ) -> dict[str, Any]:
        """Analyse dynagraph card and recommend optimised SPM and stroke length.

        Args:
            dynagraph_card: Dict with dynagraph card data including SPM and stroke length.
            target_fillage_pct: Target pump fillage percentage in (0, 100].
            max_spm: Positive maximum allowable strokes per minute.
            spm_field: Historian tag name for current strokes-per-minute in the card.
            stroke_field: Historian tag name for stroke length (inches) in the card.

        Returns:
            Dict with ``recommended_spm`` (float), ``recommended_stroke_in`` (float),
            and ``fillage_pct`` (float).

        Raises:
            KeyError: If dynagraph_card is missing the spm_field or stroke_field key.
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
        for field in (spm_field, stroke_field):
            if field not in dynagraph_card:
                raise KeyError(
                    f"RodPumpOptimizer: dynagraph_card missing required field '{field}'; "
                    f"got: {list(dynagraph_card)}"
                )
        current_spm = float(dynagraph_card[spm_field])
        stroke_length_in = float(dynagraph_card[stroke_field])
        recommended_spm = min(current_spm * (target_fillage_pct / 100.0), max_spm)
        return {
            "recommended_spm": recommended_spm,
            "recommended_stroke_in": stroke_length_in,
            "fillage_pct": target_fillage_pct,
        }
