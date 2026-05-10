"""``WaterCutTracker`` — derive water-cut time-series from oil and water rates.

Algorithm:
    1. Receive aligned oil-rate and water-rate ScadaPayloads.
    2. For each aligned sample, compute the water-cut fraction.
    3. Return a ScadaPayload of water-cut fraction values.

Math:
    Water-cut fraction at time :math:`t`:

    $$f_w(t) = \\frac{q_w(t)}{q_o(t) + q_w(t)}$$

    where :math:`q_w(t)` is water rate (bbl/day) and :math:`q_o(t)` is oil
    rate (bbl/day). Values range from 0 (no water) to 1 (100 % water).

References:
    - Craft, B.C. & Hawkins, M.F. (1959). *Applied Petroleum Reservoir
      Engineering*. Prentice-Hall, Chapter 10 (water-cut definition).
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_payload import ScadaPayload
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


def _compute_water_cut(
    oil_values: np.ndarray,
    water_values: np.ndarray,
    n: int,
) -> np.ndarray:
    wc = water_values[:n] / (oil_values[:n] + water_values[:n] + 1e-9)
    return np.clip(wc, 0.0, 1.0)


class WaterCutTracker(Knot):
    """Compute water-cut = water_rate / (water_rate + oil_rate)."""

    def __init__(
        self,
        *,
        oil_rate: Knot,
        water_rate: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(oil_rate=oil_rate, water_rate=water_rate, _config=_config, **kwargs)

    async def process(
        self,
        oil_rate: ScadaPayload,
        water_rate: ScadaPayload,
        **_: Any,
    ) -> ScadaPayload:
        """Accept oil and water rate payloads and return the computed water-cut fraction time series.

        Args:
            oil_rate: ScadaPayload of oil production rates.
            water_rate: ScadaPayload of water production rates aligned to
                the same timestamps as oil_rate.

        Returns:
            ScadaPayload of water-cut fraction values with sensor_id
            ``watercut:<oil_sensor_id>:<water_sensor_id>``.
        """
        if not isinstance(oil_rate, ScadaPayload):
            raise TypeError("WaterCutTracker: oil_rate must be a ScadaPayload")
        if not isinstance(water_rate, ScadaPayload):
            raise TypeError("WaterCutTracker: water_rate must be a ScadaPayload")
        n = min(len(oil_rate.values), len(water_rate.values))
        wc = await asyncio.to_thread(_compute_water_cut, oil_rate.values, water_rate.values, n)
        sensor_id = f"watercut:{oil_rate.series.sensor_id}:{water_rate.series.sensor_id}"
        return ScadaPayload(
            metadata=ScadaTimeSeries(
                sensor_id=sensor_id,
                sample_count=n,
                sample_interval_sec=oil_rate.series.sample_interval_sec,
            ),
            data=wc,
        )
