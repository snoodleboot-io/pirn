"""``WaterInjectionTracker`` — track injected water volumes by injector.

Algorithm:
    1. Receive an injection-rate ScadaTimeSeries.
    2. Integrate the rate over time using the trapezoidal rule.
    3. Return a cumulative injected-volume ScadaTimeSeries.

Math:
    Cumulative injected volume up to time :math:`T`:

    $$V_{\\text{cum}}(T) = \\int_0^T q_{\\text{inj}}(t)\\, dt \\approx \\sum_{i} q_{\\text{inj},i} \\cdot \\Delta t$$

    where :math:`q_{\\text{inj},i}` is the injection rate at step :math:`i`
    (bbl/day) and :math:`\\Delta t` is the sample interval (days).

References:
    - Ahmed, T. (2010). *Reservoir Engineering Handbook*, 4th ed. Gulf
      Professional Publishing, Chapter 14 (water injection and pressure
      maintenance).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class WaterInjectionTracker(Knot):
    """Compute cumulative injected volume from an injection-rate series."""

    def __init__(
        self,
        *,
        injection_rate: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            injection_rate=injection_rate, _config=_config, **kwargs
        )

    async def process(
        self, injection_rate: ScadaTimeSeries, **_: Any
    ) -> ScadaTimeSeries:
        """Accept an injection-rate series and return the cumulative injected volume as a time series.

        Args:
            injection_rate: SCADA time series containing instantaneous injection-rate samples.

        Returns:
            ScadaTimeSeries with cumulative injected volume keyed by a ``cumulative_inj:`` sensor ID.
        """
        return ScadaTimeSeries(
            sensor_id=f"cumulative_inj:{injection_rate.sensor_id}",
            sample_count=injection_rate.sample_count,
            sample_interval_sec=injection_rate.sample_interval_sec,
        )
