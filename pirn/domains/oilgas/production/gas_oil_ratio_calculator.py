"""``GasOilRatioCalculator`` — compute GOR from oil- and gas-rate series.

Algorithm:
    1. Receive aligned oil-rate and gas-rate ScadaTimeSeries.
    2. For each aligned sample, divide the gas rate by the oil rate.
    3. Return a ScadaTimeSeries of GOR values.

Math:
    Gas-oil ratio at time :math:`t`:

    $$\\text{GOR}(t) = \\frac{q_g(t)}{q_o(t)} \\quad [\\text{scf/bbl}]$$

    where :math:`q_g(t)` is gas rate (scf/day) and :math:`q_o(t)` is oil
    rate (bbl/day).

References:
    - Ahmed, T. (2010). *Reservoir Engineering Handbook*, 4th ed. Gulf
      Professional Publishing, Chapter 1 (GOR definition and field units).
"""

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
        super().__init__(oil_rate=oil_rate, gas_rate=gas_rate, _config=_config, **kwargs)

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
