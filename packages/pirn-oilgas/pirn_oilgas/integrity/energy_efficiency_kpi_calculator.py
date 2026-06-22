"""``EnergyEfficiencyKpiCalculator`` — compute energy / production efficiency KPIs.

Algorithm:
    1. Receive aligned ScadaPayloads for energy consumption (kWh) and
       hydrocarbon production (boe).
    2. Sum energy and production over the common period.
    3. Compute kWh/boe and normalise to an energy intensity index.
    4. Return a dict with ``kwh_per_boe`` and ``energy_intensity_index``.

Math:
    $$\\text{kWh/boe} = \\frac{\\sum_t E(t)}{\\sum_t P(t)}$$

    $$\\text{EII} = \\frac{\\text{kWh/boe}}{\\text{kWh/boe}_{\\text{baseline}}}$$

    where :math:`E(t)` is energy consumed at time :math:`t` (kWh) and
    :math:`P(t)` is production at time :math:`t` (boe).

References:
    - IOGP Report 2019e — Energy Efficiency in Oil and Gas Operations.
    - API RP 100-2 — Hydraulic Fracturing — Well Integrity and Fracture
      Containment, Appendix D (energy monitoring KPIs).
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.scada_payload import ScadaPayload

# IOGP 2019e baseline for onshore oil production facilities (kWh per boe).
_baseline_kwh_per_boe = 25.0


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
        energy_consumption: ScadaPayload,
        production: ScadaPayload,
        **_: Any,
    ) -> dict[str, float]:
        """Compute kWh/boe and energy intensity index from the energy and production time series and return the KPI dict.

        Args:
            energy_consumption: ScadaPayload of energy consumption readings
                (kWh) aligned to the production period.
            production: ScadaPayload of hydrocarbon production volumes (boe)
                over the same period.

        Returns:
            Dict with ``kwh_per_boe`` and ``energy_intensity_index`` KPI values.
        """
        if not isinstance(energy_consumption, ScadaPayload):
            raise TypeError(
                "EnergyEfficiencyKpiCalculator: energy_consumption must be a ScadaPayload"
            )
        if not isinstance(production, ScadaPayload):
            raise TypeError("EnergyEfficiencyKpiCalculator: production must be a ScadaPayload")

        return await asyncio.to_thread(
            self._compute,
            energy_consumption,
            production,
        )

    @staticmethod
    def _compute(energy_consumption: ScadaPayload, production: ScadaPayload) -> dict[str, float]:
        aligned_count = min(len(energy_consumption.values), len(production.values))

        # Sample values are instantaneous readings (kW and bbl/day respectively);
        # multiply by interval duration to convert to energy (kWh) and volume (boe).
        e_interval_hr = energy_consumption.series.sample_interval_sec / 3600.0
        p_interval_day = production.series.sample_interval_sec / 86400.0

        total_kwh = float(np.sum(energy_consumption.values[:aligned_count]) * e_interval_hr)
        total_boe = float(np.sum(production.values[:aligned_count]) * p_interval_day)

        kwh_per_boe = total_kwh / (total_boe + 1e-9)
        eii = kwh_per_boe / _baseline_kwh_per_boe

        return {
            "kwh_per_boe": float(kwh_per_boe),
            "energy_intensity_index": float(eii),
        }
