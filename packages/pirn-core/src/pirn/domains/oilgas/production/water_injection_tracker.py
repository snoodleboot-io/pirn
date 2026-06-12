"""``WaterInjectionTracker`` — track injected water volumes by injector.

Algorithm:
    1. Receive an injection-rate ScadaPayload.
    2. Integrate the rate over time using the trapezoidal rule.
    3. Return a cumulative injected-volume ScadaPayload.

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

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_payload import ScadaPayload
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
        super().__init__(injection_rate=injection_rate, _config=_config, **kwargs)

    async def process(self, injection_rate: ScadaPayload, **_: Any) -> ScadaPayload:
        """Accept an injection-rate payload and return the cumulative injected volume as a time series.

        Args:
            injection_rate: ScadaPayload containing instantaneous injection-rate samples.

        Returns:
            ScadaPayload with cumulative injected volume keyed by a ``cumulative_inj:`` sensor ID.
        """
        if not isinstance(injection_rate, ScadaPayload):
            raise TypeError("WaterInjectionTracker: injection_rate must be a ScadaPayload")
        cum = np.cumsum(injection_rate.values * injection_rate.series.sample_interval_sec / 86400)
        sensor_id = f"cumulative_inj:{injection_rate.series.sensor_id}"
        return ScadaPayload(
            metadata=ScadaTimeSeries(
                sensor_id=sensor_id,
                sample_count=len(cum),
                sample_interval_sec=injection_rate.series.sample_interval_sec,
            ),
            data=cum,
        )
