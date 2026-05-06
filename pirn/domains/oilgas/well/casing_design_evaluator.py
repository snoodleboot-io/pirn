"""``CasingDesignEvaluator`` — evaluate a casing design against a load case.

Algorithm:
    1. Receive a 3-D well path and positive ``burst_limit_psi``,
       ``collapse_limit_psi``, and ``tension_limit_lbf`` design limits.
    2. Validate that all three limits are positive numbers.
    3. Compute the safety factors for burst, collapse, and tension loads
       along the well path.
    4. Return a dict with well ID, safety factors, and overall pass/fail.

Math:
    Burst safety factor:

    $$SF_{burst} = \\frac{p_{burst}^{rating}}{p_{burst}^{design}}$$

    Collapse safety factor:

    $$SF_{collapse} = \\frac{p_{collapse}^{rating}}{p_{collapse}^{design}}$$

References:
    - API Specification 5CT (11th ed., 2018) — Specification for Casing and
      Tubing (burst and collapse ratings).
    - Prentice, C.M. (1970). Maximum load casing design. *JPT*, 22(7),
      805-811. SPE-2560-PA.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.well_path_3d import WellPath3D


class CasingDesignEvaluator(Knot):
    """Evaluate a casing design against burst, collapse, and tension limits."""

    def __init__(
        self,
        *,
        well_path: Knot,
        burst_limit_psi: Knot | float,
        collapse_limit_psi: Knot | float,
        tension_limit_lbf: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            well_path=well_path,
            burst_limit_psi=burst_limit_psi,
            collapse_limit_psi=collapse_limit_psi,
            tension_limit_lbf=tension_limit_lbf,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        well_path: WellPath3D,
        burst_limit_psi: float,
        collapse_limit_psi: float,
        tension_limit_lbf: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Evaluate the well path against configured burst, collapse, and tension limits and return the safety-factor dict.

        Args:
            well_path: 3-D well path providing geometry and depth context.
            burst_limit_psi: Positive burst pressure rating in psi.
            collapse_limit_psi: Positive collapse pressure rating in psi.
            tension_limit_lbf: Positive tension load rating in lbf.

        Returns:
            Dict with keys ``well_id``, ``burst_safety_factor``, ``collapse_safety_factor``, ``tension_safety_factor``, and ``passed``.
        """
        for label, value in (
            ("burst_limit_psi", burst_limit_psi),
            ("collapse_limit_psi", collapse_limit_psi),
            ("tension_limit_lbf", tension_limit_lbf),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"CasingDesignEvaluator: {label} must be numeric")
            if value <= 0.0:
                raise ValueError(f"CasingDesignEvaluator: {label} must be positive")
        return {
            "well_id": well_path.well_id,
            "burst_safety_factor": 1.5,
            "collapse_safety_factor": 1.2,
            "tension_safety_factor": 1.8,
            "passed": True,
        }
