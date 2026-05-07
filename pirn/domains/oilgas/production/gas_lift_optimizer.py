"""``GasLiftOptimizer`` — optimize gas injection rate to maximize oil production from gas-lifted wells.

Algorithm:
    1. Receive well data dict, ``injection_gas_cost_per_mscf``, and
       ``max_injection_rate_mmscfd``.
    2. Validate that cost and max-rate are positive.
    3. Scan the performance curve to find the injection rate that maximises
       oil production subject to the maximum injection constraint.
    4. Return optimal injection rate, projected oil rate, and incremental uplift.

Math:
    Performance-curve optimisation:

    $$q_{\\text{inj}}^* = \\arg\\max_{q \\leq q_{\\max}} q_o(q_{\\text{inj}})$$

    where :math:`q_o(q_{\\text{inj}})` is the oil production rate at injection
    rate :math:`q_{\\text{inj}}` (read from the empirical performance curve).

    Economic optimum (net revenue maximisation):

    $$q_{\\text{inj}}^{\\text{econ}} = \\arg\\max_{q} \\left[ p_o \\cdot q_o(q) - c_{\\text{inj}} \\cdot q \\right]$$

References:
    - Camponogara, E. & Nakashima, P.H. (2006). Solving a gas-lift optimization
      problem by dynamic programming. *European Journal of Operational Research*,
      174(3), 1220-1246.
    - Takacs, G. (2005). *Gas Lift Manual*. PennWell Corporation, Chapter 5.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class GasLiftOptimizer(Knot):
    """Select the optimal gas injection rate on the performance curve for a gas-lifted well."""

    def __init__(
        self,
        *,
        well_data: Knot,
        injection_gas_cost_per_mscf: Knot | float,
        max_injection_rate_mmscfd: Knot | float,
        curve_field: Knot | str = "performance_curve",
        current_injection_field: Knot | str = "current_injection_mmscfd",
        point_injection_field: Knot | str = "injection_mmscfd",
        point_oil_field: Knot | str = "oil_bopd",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            well_data=well_data,
            injection_gas_cost_per_mscf=injection_gas_cost_per_mscf,
            max_injection_rate_mmscfd=max_injection_rate_mmscfd,
            curve_field=curve_field,
            current_injection_field=current_injection_field,
            point_injection_field=point_injection_field,
            point_oil_field=point_oil_field,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        well_data: dict[str, Any],
        injection_gas_cost_per_mscf: float,
        max_injection_rate_mmscfd: float,
        curve_field: str = "performance_curve",
        current_injection_field: str = "current_injection_mmscfd",
        point_injection_field: str = "injection_mmscfd",
        point_oil_field: str = "oil_bopd",
        **_: Any,
    ) -> dict[str, Any]:
        """Find the optimal injection rate on the well performance curve.

        Args:
            well_data: Dict containing the performance curve and current injection rate.
            injection_gas_cost_per_mscf: Positive cost of injection gas per MSCF.
            max_injection_rate_mmscfd: Positive maximum injection rate in MMSCFD.
            curve_field: Key for the performance curve list in well_data.
            current_injection_field: Key for the current injection rate in well_data.
            point_injection_field: Key for injection rate in each curve point dict.
            point_oil_field: Key for oil rate in each curve point dict.

        Returns:
            Dict with ``optimal_injection_mmscfd`` (float),
            ``projected_oil_bopd`` (float), and ``incremental_bopd`` (float).

        Raises:
            KeyError: If well_data or any curve point is missing a required field.
        """
        for label, value in (
            ("injection_gas_cost_per_mscf", injection_gas_cost_per_mscf),
            ("max_injection_rate_mmscfd", max_injection_rate_mmscfd),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"GasLiftOptimizer: {label} must be numeric")
            if value <= 0:
                raise ValueError(f"GasLiftOptimizer: {label} must be positive")
        if not isinstance(well_data, dict):
            raise TypeError("GasLiftOptimizer: well_data must be a dict")
        for field in (curve_field, current_injection_field):
            if field not in well_data:
                raise KeyError(
                    f"GasLiftOptimizer: well_data missing required field '{field}'; "
                    f"got: {list(well_data)}"
                )
        curve: list[dict[str, Any]] = well_data[curve_field]
        current_injection = float(well_data[current_injection_field])
        best_injection = current_injection
        best_oil = 0.0
        for j, point in enumerate(curve):
            for field in (point_injection_field, point_oil_field):
                if field not in point:
                    raise KeyError(
                        f"GasLiftOptimizer: curve[{j}] missing required field '{field}'; "
                        f"got: {list(point)}"
                    )
            inj = float(point[point_injection_field])
            oil = float(point[point_oil_field])
            if inj <= max_injection_rate_mmscfd and oil > best_oil:
                best_oil = oil
                best_injection = inj
        current_oil = next(
            (
                float(p[point_oil_field])
                for p in curve
                if float(p[point_injection_field]) == current_injection
            ),
            0.0,
        )
        return {
            "optimal_injection_mmscfd": best_injection,
            "projected_oil_bopd": best_oil,
            "incremental_bopd": max(0.0, best_oil - current_oil),
        }
