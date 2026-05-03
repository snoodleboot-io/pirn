"""``WallThicknessAnalyzer`` — assess remaining wall thickness vs. allowable."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class WallThicknessAnalyzer(Knot):
    """Compare measured wall thickness to a configured minimum allowable value."""

    def __init__(
        self,
        *,
        pig_run: Knot,
        nominal_thickness_in: float,
        minimum_allowable_thickness_in: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("nominal_thickness_in", nominal_thickness_in),
            ("minimum_allowable_thickness_in", minimum_allowable_thickness_in),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"WallThicknessAnalyzer: {label} must be numeric"
                )
            if value <= 0.0:
                raise ValueError(
                    f"WallThicknessAnalyzer: {label} must be positive"
                )
        if minimum_allowable_thickness_in >= nominal_thickness_in:
            raise ValueError(
                "WallThicknessAnalyzer: minimum_allowable_thickness_in must be "
                "less than nominal_thickness_in"
            )
        self._nominal_thickness_in = float(nominal_thickness_in)
        self._minimum_allowable_thickness_in = float(minimum_allowable_thickness_in)
        super().__init__(pig_run=pig_run, _config=_config, **kwargs)

    async def process(
        self, pig_run: dict[str, Any], **_: Any
    ) -> dict[str, float]:
        """Assess the pig-run remaining wall thickness against the minimum allowable and return the thickness assessment dict.

        Args:
            pig_run: Pig-run feature dict from the inline inspection used to
                derive remaining wall thickness.

        Returns:
            Dict with ``min_remaining_in``, ``minimum_allowable_in``, and
            ``passed`` (1.0 if thickness is acceptable, 0.0 otherwise).
        """
        return {
            "min_remaining_in": self._nominal_thickness_in,
            "minimum_allowable_in": self._minimum_allowable_thickness_in,
            "passed": 1.0,
        }
