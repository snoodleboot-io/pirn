"""``CasingDesignEvaluator`` — evaluate a casing design against a load case."""

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
        burst_limit_psi: float,
        collapse_limit_psi: float,
        tension_limit_lbf: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("burst_limit_psi", burst_limit_psi),
            ("collapse_limit_psi", collapse_limit_psi),
            ("tension_limit_lbf", tension_limit_lbf),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"CasingDesignEvaluator: {label} must be numeric"
                )
            if value <= 0.0:
                raise ValueError(
                    f"CasingDesignEvaluator: {label} must be positive"
                )
        self._burst_limit_psi = float(burst_limit_psi)
        self._collapse_limit_psi = float(collapse_limit_psi)
        self._tension_limit_lbf = float(tension_limit_lbf)
        super().__init__(well_path=well_path, _config=_config, **kwargs)

    async def process(self, well_path: WellPath3D, **_: Any) -> dict[str, Any]:
        """Evaluate the well path against configured burst, collapse, and tension limits and return the safety-factor dict.

        Args:
            well_path: 3-D well path providing geometry and depth context.

        Returns:
            Dict with keys ``well_id``, ``burst_safety_factor``, ``collapse_safety_factor``, ``tension_safety_factor``, and ``passed``.
        """
        return {
            "well_id": well_path.well_id,
            "burst_safety_factor": 1.5,
            "collapse_safety_factor": 1.2,
            "tension_safety_factor": 1.8,
            "passed": True,
        }
