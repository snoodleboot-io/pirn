"""``GasOilRatioCalculator`` — compute GOR from oil- and gas-rate series."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class GasOilRatioCalculator(Knot):
    """Compute the gas-oil ratio time-series from oil and gas rate inputs."""

    def __init__(
        self,
        *,
        oil_rate: Knot,
        gas_rate: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            oil_rate=oil_rate, gas_rate=gas_rate, _config=_config, **kwargs
        )

    async def process(
        self,
        oil_rate: ScadaTimeSeries,
        gas_rate: ScadaTimeSeries,
        **_: Any,
    ) -> ScadaTimeSeries:
        """Accept oil and gas rate series and return the computed gas-oil ratio time series.

        Args:
            oil_rate: ScadaTimeSeries of oil production rates.
            gas_rate: ScadaTimeSeries of gas production rates aligned to the
                same timestamps as oil_rate.

        Returns:
            ScadaTimeSeries of gas-oil ratio values with sensor_id
            ``gor:<oil_sensor_id>:<gas_sensor_id>``.
        """
        return ScadaTimeSeries(
            sensor_id=f"gor:{oil_rate.sensor_id}:{gas_rate.sensor_id}",
            sample_interval_sec=oil_rate.sample_interval_sec,
        )
