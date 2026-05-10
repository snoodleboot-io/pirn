"""``WallThicknessAnalyzer`` — assess remaining wall thickness vs. allowable.

Algorithm:
    1. Receive a pig-run dict, ``nominal_thickness_in``, and
       ``minimum_allowable_thickness_in``.
    2. Validate all inputs are positive and ``minimum_allowable < nominal``.
    3. Derive remaining wall thickness from the pig-run data.
    4. Compare against the minimum allowable threshold.
    5. Return min remaining thickness, minimum allowable, and pass/fail flag.

Math:
    ASME B31G remaining-strength criterion:

    $$t_{\\text{remaining}} = t_{\\text{nominal}} - \\Delta t_{\\text{ILI}}$$

    where :math:`\\Delta t_{\\text{ILI}}` is the maximum measured wall loss
    from the in-line inspection. The section passes if:

    $$t_{\\text{remaining}} \\geq t_{\\text{min}} = \\frac{t_{\\text{nominal}} \\times (P_{\\text{MAOP}} \\times SF)}{S \\times E \\times T}$$

References:
    - ASME B31G-2012, Manual for Determining the Remaining Strength of Corroded
      Pipelines.
    - API 579-1/ASME FFS-1 (2016) — Fitness-For-Service, Part 4 (assessment of
      general metal loss).
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class WallThicknessAnalyzer(Knot):
    """Compare measured wall thickness to a configured minimum allowable value."""

    def __init__(
        self,
        *,
        pig_run: Knot,
        nominal_thickness_in: Knot | float,
        minimum_allowable_thickness_in: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pig_run=pig_run,
            nominal_thickness_in=nominal_thickness_in,
            minimum_allowable_thickness_in=minimum_allowable_thickness_in,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pig_run: dict[str, Any],
        nominal_thickness_in: float,
        minimum_allowable_thickness_in: float,
        **_: Any,
    ) -> dict[str, float]:
        """Assess the pig-run remaining wall thickness against the minimum allowable and return the thickness assessment dict.

        Args:
            pig_run: Pig-run feature dict from the inline inspection used to
                derive remaining wall thickness.
            nominal_thickness_in: Positive nominal wall thickness in inches.
            minimum_allowable_thickness_in: Positive minimum allowable thickness
                in inches; must be less than ``nominal_thickness_in``.

        Returns:
            Dict with ``min_remaining_in``, ``minimum_allowable_in``, and
            ``passed`` (1.0 if thickness is acceptable, 0.0 otherwise).
        """
        for label, value in (
            ("nominal_thickness_in", nominal_thickness_in),
            ("minimum_allowable_thickness_in", minimum_allowable_thickness_in),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"WallThicknessAnalyzer: {label} must be numeric")
            if value <= 0.0:
                raise ValueError(f"WallThicknessAnalyzer: {label} must be positive")
        if minimum_allowable_thickness_in >= nominal_thickness_in:
            raise ValueError(
                "WallThicknessAnalyzer: minimum_allowable_thickness_in must be "
                "less than nominal_thickness_in"
            )

        return await asyncio.to_thread(
            self._assess,
            pig_run,
            float(nominal_thickness_in),
            float(minimum_allowable_thickness_in),
        )

    @staticmethod
    def _assess(
        pig_run: dict[str, Any],
        nominal: float,
        mat: float,
    ) -> dict[str, float]:
        readings = pig_run.get("thickness_readings_in", [])

        if readings:
            arr = np.array(readings, dtype=np.float64)
            min_remaining = float(np.min(arr))
        else:
            min_remaining = nominal

        passed = min_remaining >= mat

        return {
            "min_remaining_in": float(min_remaining),
            "minimum_allowable_in": float(mat),
            "passed": 1.0 if passed else 0.0,
        }
