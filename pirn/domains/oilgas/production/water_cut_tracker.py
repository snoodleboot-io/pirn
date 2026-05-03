"""``WaterCutTracker`` — derive water-cut time-series from oil and water rates."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


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
        super().__init__(
            oil_rate=oil_rate, water_rate=water_rate, _config=_config, **kwargs
        )

    async def process(
        self,
        oil_rate: ScadaTimeSeries,
        water_rate: ScadaTimeSeries,
        **_: Any,
    ) -> ScadaTimeSeries:
        """Accept oil and water rate series and return the computed water-cut fraction time series.

        Args:
            oil_rate: ScadaTimeSeries of oil production rates.
            water_rate: ScadaTimeSeries of water production rates aligned to
                the same timestamps as oil_rate.

        Returns:
            ScadaTimeSeries of water-cut fraction values with sensor_id
            ``watercut:<oil_sensor_id>:<water_sensor_id>``.
        """
        return ScadaTimeSeries(
            sensor_id=f"watercut:{oil_rate.sensor_id}:{water_rate.sensor_id}",
            sample_interval_sec=oil_rate.sample_interval_sec,
        )
