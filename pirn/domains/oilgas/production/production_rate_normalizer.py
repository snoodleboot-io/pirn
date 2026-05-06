"""``ProductionRateNormalizer`` — normalize production rates to standard conditions.

Algorithm:
    1. Receive a list of measurement dicts and reference pressure / temperature.
    2. Validate that ``reference_pressure_psia`` is positive and
       ``reference_temp_f`` is numeric.
    3. For each measurement, compute the Boyle-Charles correction factor.
    4. Multiply the observed rate by the correction factor.
    5. Return augmented measurement dicts with ``normalized_rate_bopd``.

Math:
    Combined Boyle-Charles correction (ideal gas approximation):

    $$q_{\\text{norm}} = q_{\\text{obs}} \\times \\frac{P_{\\text{wh}}}{P_{\\text{ref}}} \\times \\frac{T_{\\text{ref}}}{T_{\\text{wh}}}$$

    where temperatures are in Rankine (:math:`T_R = T_{\\text{°F}} + 459.67`).

References:
    - API MPMS Chapter 11.1 — Temperature and Pressure Volume Correction
      Factors for Generalized Crude Oils.
    - Ahmed, T. (2010). *Reservoir Engineering Handbook*, 4th ed. Gulf
      Professional Publishing, Appendix A (equation-of-state corrections).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ProductionRateNormalizer(Knot):
    """Normalize wellhead production rates to reference temperature and pressure conditions."""

    def __init__(
        self,
        *,
        measurements: Knot,
        reference_pressure_psia: Knot | float,
        reference_temp_f: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            measurements=measurements,
            reference_pressure_psia=reference_pressure_psia,
            reference_temp_f=reference_temp_f,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        measurements: list[dict[str, Any]],
        reference_pressure_psia: float,
        reference_temp_f: float,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Normalize each measurement's rate to reference conditions.

        Args:
            measurements: List of dicts with ``rate_bopd``, ``wellhead_pressure_psia``,
                and ``wellhead_temp_f``.
            reference_pressure_psia: Positive reference pressure in psia.
            reference_temp_f: Reference temperature in degrees Fahrenheit.

        Returns:
            List of dicts with the same keys plus ``normalized_rate_bopd``.
        """
        if not isinstance(reference_pressure_psia, (int, float)):
            raise TypeError("ProductionRateNormalizer: reference_pressure_psia must be numeric")
        if reference_pressure_psia <= 0:
            raise ValueError("ProductionRateNormalizer: reference_pressure_psia must be positive")
        if not isinstance(reference_temp_f, (int, float)):
            raise TypeError("ProductionRateNormalizer: reference_temp_f must be numeric")
        ref_t_rankine = float(reference_temp_f) + 459.67
        ref_p = float(reference_pressure_psia)
        results: list[dict[str, Any]] = []
        for m in measurements:
            rate = float(m.get("rate_bopd", 0.0))
            wh_p = float(m.get("wellhead_pressure_psia", ref_p))
            wh_t = float(m.get("wellhead_temp_f", reference_temp_f))
            wh_t_rankine = wh_t + 459.67
            correction = (wh_p / ref_p) * (ref_t_rankine / wh_t_rankine)
            normalized = rate * correction
            results.append({**m, "normalized_rate_bopd": normalized})
        return results
