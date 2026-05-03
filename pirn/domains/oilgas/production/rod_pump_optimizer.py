"""``RodPumpOptimizer`` — optimize rod pump stroke length and speed for sucker-rod lifted wells."""

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
        target_fillage_pct: float,
        max_spm: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(target_fillage_pct, (int, float)):
            raise TypeError("RodPumpOptimizer: target_fillage_pct must be numeric")
        if not (0 < target_fillage_pct <= 100):
            raise ValueError(
                "RodPumpOptimizer: target_fillage_pct must be in (0, 100]"
            )
        if not isinstance(max_spm, (int, float)):
            raise TypeError("RodPumpOptimizer: max_spm must be numeric")
        if max_spm <= 0:
            raise ValueError("RodPumpOptimizer: max_spm must be positive")
        self._target_fillage_pct = float(target_fillage_pct)
        self._max_spm = float(max_spm)
        super().__init__(dynagraph_card=dynagraph_card, _config=_config, **kwargs)

    async def process(self, dynagraph_card: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Analyse dynagraph card and recommend optimised SPM and stroke length.

        Args:
            dynagraph_card: Dict with ``surface_load_lbf`` (list[float]),
                ``surface_position_in`` (list[float]), ``current_spm``,
                and ``stroke_length_in``.

        Returns:
            Dict with ``recommended_spm`` (float), ``recommended_stroke_in`` (float),
            and ``fillage_pct`` (float).
        """
        if not isinstance(dynagraph_card, dict):
            raise TypeError("RodPumpOptimizer: dynagraph_card must be a dict")
        current_spm = float(dynagraph_card.get("current_spm", self._max_spm))
        stroke_length_in = float(dynagraph_card.get("stroke_length_in", 144.0))
        recommended_spm = min(current_spm * (self._target_fillage_pct / 100.0), self._max_spm)
        return {
            "recommended_spm": recommended_spm,
            "recommended_stroke_in": stroke_length_in,
            "fillage_pct": self._target_fillage_pct,
        }
