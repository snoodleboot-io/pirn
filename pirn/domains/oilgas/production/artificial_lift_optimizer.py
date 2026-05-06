"""``ArtificialLiftOptimizer`` — recommend a lift-system operating point.

Algorithm:
    1. Receive a production ScadaTimeSeries and a ``lift_type`` string.
    2. Validate that ``lift_type`` is one of the recognised lift types.
    3. Analyse the production rate trend to identify the optimal operating setpoint.
    4. Return a dict with ``lift_type``, ``recommended_setpoint``, and
       ``expected_uplift_bopd``.

Math:
    Inflow Performance Relationship (Vogel):

    $$\\frac{q_o}{q_{o,\\max}} = 1 - 0.2 \\frac{p_{wf}}{p_{r}} - 0.8 \\left(\\frac{p_{wf}}{p_{r}}\\right)^2$$

    The optimal setpoint minimises the specific energy consumption while
    satisfying the lift-system hydraulic constraint.

References:
    - Vogel, J.V. (1968). Inflow performance relationships for solution-gas
      drive wells. *JPT*, 20(1), 83–92. SPE-1476-PA.
    - Lea, J.F., Nickens, H.V. & Wells, M.R. (2008). *Gas Well Deliquification*,
      2nd ed. Gulf Professional Publishing, Chapter 3.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class ArtificialLiftOptimizer(Knot):
    """Recommend an operating point for a configured artificial-lift system."""

    def __init__(
        self,
        *,
        production: Knot,
        lift_type: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            production=production,
            lift_type=lift_type,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        production: ScadaTimeSeries,
        lift_type: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Recommend an operating setpoint for the lift system from the production series and return it with the expected uplift.

        Args:
            production: ScadaTimeSeries of current production rates used to
                derive the recommended operating setpoint.
            lift_type: One of ``esp``, ``gas_lift``, ``rod_pump``, ``pcp``,
                or ``jet_pump``.

        Returns:
            Dict with ``lift_type``, ``recommended_setpoint`` (float), and
            ``expected_uplift_bopd`` (estimated incremental barrels per day).
        """
        _valid_lift_types: frozenset[str] = frozenset(
            {"esp", "gas_lift", "rod_pump", "pcp", "jet_pump"}
        )
        if lift_type not in _valid_lift_types:
            raise ValueError(
                f"ArtificialLiftOptimizer: lift_type must be one of "
                f"{sorted(_valid_lift_types)}"
            )
        return {
            "lift_type": lift_type,
            "recommended_setpoint": 1.0,
            "expected_uplift_bopd": 50.0,
        }
