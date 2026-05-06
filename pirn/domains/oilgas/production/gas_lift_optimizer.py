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


class GasLiftOptimizer(Knot):
    """Select the optimal gas injection rate on the performance curve for a gas-lifted well."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    async def process(
        self,
        well_data: dict[str, Any],
        injection_gas_cost_per_mscf: float,
        max_injection_rate_mmscfd: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Find the optimal injection rate on the well performance curve.

        Args:
            well_data: Dict with ``current_injection_mmscfd`` and
                ``performance_curve`` (list of dicts with ``injection_mmscfd``
                and ``oil_bopd``).
            injection_gas_cost_per_mscf: Positive cost of injection gas per MSCF.
            max_injection_rate_mmscfd: Positive maximum injection rate in MMSCFD.

        Returns:
            Dict with ``optimal_injection_mmscfd`` (float),
            ``projected_oil_bopd`` (float), and ``incremental_bopd`` (float).
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
        curve: list[dict[str, Any]] = well_data.get("performance_curve", [])
        current_injection = float(well_data.get("current_injection_mmscfd", 0.0))
        best_injection = current_injection
        best_oil = 0.0
        for point in curve:
            inj = float(point.get("injection_mmscfd", 0.0))
            oil = float(point.get("oil_bopd", 0.0))
            if inj <= max_injection_rate_mmscfd and oil > best_oil:
                best_oil = oil
                best_injection = inj
        current_oil = next(
            (
                float(p["oil_bopd"])
                for p in curve
                if float(p.get("injection_mmscfd", -1)) == current_injection
            ),
            0.0,
        )
        return {
            "optimal_injection_mmscfd": best_injection,
            "projected_oil_bopd": best_oil,
            "incremental_bopd": max(0.0, best_oil - current_oil),
        }
