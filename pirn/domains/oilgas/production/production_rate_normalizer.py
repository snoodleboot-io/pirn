"""``ProductionRateNormalizer`` — normalize production rates to standard conditions."""

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
        reference_pressure_psia: float,
        reference_temp_f: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(reference_pressure_psia, (int, float)):
            raise TypeError(
                "ProductionRateNormalizer: reference_pressure_psia must be numeric"
            )
        if reference_pressure_psia <= 0:
            raise ValueError(
                "ProductionRateNormalizer: reference_pressure_psia must be positive"
            )
        if not isinstance(reference_temp_f, (int, float)):
            raise TypeError(
                "ProductionRateNormalizer: reference_temp_f must be numeric"
            )
        self._reference_pressure_psia = float(reference_pressure_psia)
        self._reference_temp_f = float(reference_temp_f)
        super().__init__(measurements=measurements, _config=_config, **kwargs)

    async def process(
        self, measurements: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Normalize each measurement's rate to reference conditions.

        Args:
            measurements: List of dicts with ``rate_bopd``, ``wellhead_pressure_psia``,
                and ``wellhead_temp_f``.

        Returns:
            List of dicts with the same keys plus ``normalized_rate_bopd``.
        """
        results: list[dict[str, Any]] = []
        ref_t_rankine = self._reference_temp_f + 459.67
        ref_p = self._reference_pressure_psia
        for m in measurements:
            rate = float(m.get("rate_bopd", 0.0))
            wh_p = float(m.get("wellhead_pressure_psia", ref_p))
            wh_t = float(m.get("wellhead_temp_f", self._reference_temp_f))
            wh_t_rankine = wh_t + 459.67
            correction = (wh_p / ref_p) * (ref_t_rankine / wh_t_rankine)
            normalized = rate * correction
            results.append({**m, "normalized_rate_bopd": normalized})
        return results
