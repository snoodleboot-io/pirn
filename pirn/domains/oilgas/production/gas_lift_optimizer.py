"""``GasLiftOptimizer`` — optimize gas injection rate to maximize oil production from gas-lifted wells."""

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
        injection_gas_cost_per_mscf: float,
        max_injection_rate_mmscfd: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("injection_gas_cost_per_mscf", injection_gas_cost_per_mscf),
            ("max_injection_rate_mmscfd", max_injection_rate_mmscfd),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(f"GasLiftOptimizer: {label} must be numeric")
            if value <= 0:
                raise ValueError(f"GasLiftOptimizer: {label} must be positive")
        self._injection_gas_cost_per_mscf = float(injection_gas_cost_per_mscf)
        self._max_injection_rate_mmscfd = float(max_injection_rate_mmscfd)
        super().__init__(well_data=well_data, _config=_config, **kwargs)

    async def process(self, well_data: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Find the optimal injection rate on the well performance curve.

        Args:
            well_data: Dict with ``current_injection_mmscfd`` and
                ``performance_curve`` (list of dicts with ``injection_mmscfd``
                and ``oil_bopd``).

        Returns:
            Dict with ``optimal_injection_mmscfd`` (float),
            ``projected_oil_bopd`` (float), and ``incremental_bopd`` (float).
        """
        if not isinstance(well_data, dict):
            raise TypeError("GasLiftOptimizer: well_data must be a dict")
        curve: list[dict[str, Any]] = well_data.get("performance_curve", [])
        current_injection = float(well_data.get("current_injection_mmscfd", 0.0))
        best_injection = current_injection
        best_oil = 0.0
        for point in curve:
            inj = float(point.get("injection_mmscfd", 0.0))
            oil = float(point.get("oil_bopd", 0.0))
            if inj <= self._max_injection_rate_mmscfd and oil > best_oil:
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
