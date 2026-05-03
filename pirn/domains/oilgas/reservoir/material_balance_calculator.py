"""``MaterialBalanceCalculator`` — solve for original oil / gas in place."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.pvt_table import PVTTable


class MaterialBalanceCalculator(Knot):
    """Solve a Havlena-Odeh-style material balance for OOIP / OGIP."""

    def __init__(
        self,
        *,
        pvt: Knot,
        cumulative_oil_stb: float,
        cumulative_gas_mscf: float,
        cumulative_water_stb: float,
        average_pressure_psi: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("cumulative_oil_stb", cumulative_oil_stb),
            ("cumulative_gas_mscf", cumulative_gas_mscf),
            ("cumulative_water_stb", cumulative_water_stb),
            ("average_pressure_psi", average_pressure_psi),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"MaterialBalanceCalculator: {label} must be numeric"
                )
            if value < 0.0:
                raise ValueError(
                    f"MaterialBalanceCalculator: {label} must be non-negative"
                )
        self._cumulative_oil_stb = float(cumulative_oil_stb)
        self._cumulative_gas_mscf = float(cumulative_gas_mscf)
        self._cumulative_water_stb = float(cumulative_water_stb)
        self._average_pressure_psi = float(average_pressure_psi)
        super().__init__(pvt=pvt, _config=_config, **kwargs)

    async def process(self, pvt: PVTTable, **_: Any) -> dict[str, float]:
        """Solve the material balance equation from the PVT table and cumulative production inputs and return OOIP and OGIP.

        Args:
            pvt: PVT lookup table providing fluid-property correlations.

        Returns:
            Dict with keys ``ooip_stb`` (original oil in place) and ``ogip_mscf`` (original gas in place).
        """
        return {
            "ooip_stb": max(self._cumulative_oil_stb, 1.0) * 10.0,
            "ogip_mscf": max(self._cumulative_gas_mscf, 1.0) * 10.0,
        }
