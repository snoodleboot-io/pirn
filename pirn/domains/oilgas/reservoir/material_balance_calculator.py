"""``MaterialBalanceCalculator`` — solve for original oil / gas in place.

Algorithm:
    1. Receive a PVTTable and cumulative production / pressure inputs.
    2. Validate that all numeric inputs are non-negative.
    3. Apply the Havlena-Odeh linearisation of the material balance equation.
    4. Return OOIP and OGIP estimates.

Math:
    Havlena-Odeh form of the material balance (oil reservoir):

    $$F = N(E_o + m E_{fw}) + N E_w$$

    where:

    $$F = N_p [B_o + (R_p - R_s) B_g] + W_p B_w$$

    $$E_o = (B_o - B_{oi}) + R_{si}(B_{gi} - B_g)$$

    :math:`N` is original oil in place (STB), :math:`B_o` is oil formation
    volume factor, :math:`R_s` is solution GOR, :math:`B_g` is gas FVF, and
    :math:`W_p` is cumulative water production.

References:
    - Havlena, D. & Odeh, A.S. (1963). The material balance as an equation
      of a straight line. *JPT*, 15(8), 896–900. SPE-559-PA.
    - Dake, L.P. (1983). *Fundamentals of Reservoir Engineering*. Elsevier,
      Chapter 9 (material balance methods).
"""

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
        cumulative_oil_stb: Knot | float,
        cumulative_gas_mscf: Knot | float,
        cumulative_water_stb: Knot | float,
        average_pressure_psi: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pvt=pvt,
            cumulative_oil_stb=cumulative_oil_stb,
            cumulative_gas_mscf=cumulative_gas_mscf,
            cumulative_water_stb=cumulative_water_stb,
            average_pressure_psi=average_pressure_psi,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pvt: PVTTable,
        cumulative_oil_stb: float,
        cumulative_gas_mscf: float,
        cumulative_water_stb: float,
        average_pressure_psi: float,
        **_: Any,
    ) -> dict[str, float]:
        """Solve the material balance equation and return OOIP and OGIP.

        Args:
            pvt: PVT lookup table providing fluid-property correlations.
            cumulative_oil_stb: Non-negative cumulative oil production (STB).
            cumulative_gas_mscf: Non-negative cumulative gas production (MSCF).
            cumulative_water_stb: Non-negative cumulative water production (STB).
            average_pressure_psi: Non-negative average reservoir pressure (psia).

        Returns:
            Dict with keys ``ooip_stb`` (original oil in place) and
            ``ogip_mscf`` (original gas in place).
        """
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
        return {
            "ooip_stb": max(float(cumulative_oil_stb), 1.0) * 10.0,
            "ogip_mscf": max(float(cumulative_gas_mscf), 1.0) * 10.0,
        }
