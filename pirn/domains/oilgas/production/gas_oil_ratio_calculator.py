"""``GasOilRatioCalculator`` — compute GOR from oil- and gas-rate series.

Algorithm:
    1. Receive aligned oil-rate and gas-rate ScadaPayloads.
    2. For each aligned sample, divide the gas rate by the oil rate.
    3. Return a ScadaPayload of GOR values.

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

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_payload import ScadaPayload
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


def _compute_gor(oil_values: np.ndarray, gas_values: np.ndarray, aligned_count: int) -> np.ndarray:
    return gas_values[:aligned_count] / (oil_values[:aligned_count] + 1e-6)


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
        oil_rate: ScadaPayload,
        gas_rate: ScadaPayload,
        **_: Any,
    ) -> ScadaPayload:
        """Accept oil and gas rate payloads and return the computed gas-oil ratio time series.

        Args:
            oil_rate: ScadaPayload of oil production rates.
            gas_rate: ScadaPayload of gas production rates aligned to the
                same timestamps as oil_rate.

        Returns:
            ScadaPayload of gas-oil ratio values with sensor_id
            ``gor:<oil_sensor_id>:<gas_sensor_id>``.
        """
        if not isinstance(oil_rate, ScadaPayload):
            raise TypeError("GasOilRatioCalculator: oil_rate must be a ScadaPayload")
        if not isinstance(gas_rate, ScadaPayload):
            raise TypeError("GasOilRatioCalculator: gas_rate must be a ScadaPayload")
        aligned_count = min(len(oil_rate.values), len(gas_rate.values))
        gor = await asyncio.to_thread(_compute_gor, oil_rate.values, gas_rate.values, aligned_count)
        sensor_id = f"gor:{oil_rate.series.sensor_id}:{gas_rate.series.sensor_id}"
        return ScadaPayload(
            metadata=ScadaTimeSeries(
                sensor_id=sensor_id,
                sample_count=aligned_count,
                sample_interval_sec=oil_rate.series.sample_interval_sec,
            ),
            data=gor,
        )
