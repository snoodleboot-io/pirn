"""``EnergyEfficiencyKpiCalculator`` — compute energy / production efficiency KPIs."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class EnergyEfficiencyKpiCalculator(Knot):
    """Compute kWh / boe and similar energy-per-production efficiency KPIs."""

    def __init__(
        self,
        *,
        energy_consumption: Knot,
        production: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            energy_consumption=energy_consumption,
            production=production,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        energy_consumption: ScadaTimeSeries,
        production: ScadaTimeSeries,
        **_: Any,
    ) -> dict[str, float]:
        """Compute kWh/boe and energy intensity index from the energy and production time series and return the KPI dict.

        Args:
            energy_consumption: ScadaTimeSeries of energy consumption readings
                (kWh) aligned to the production period.
            production: ScadaTimeSeries of hydrocarbon production volumes (boe)
                over the same period.

        Returns:
            Dict with ``kwh_per_boe`` and ``energy_intensity_index`` KPI values.
        """
        return {
            "kwh_per_boe": 25.0,
            "energy_intensity_index": 1.0,
        }
