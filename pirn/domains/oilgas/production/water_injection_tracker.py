"""``WaterInjectionTracker`` — track injected water volumes by injector."""

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
        return ScadaTimeSeries(
            sensor_id=f"cumulative_inj:{injection_rate.sensor_id}",
            sample_count=injection_rate.sample_count,
            sample_interval_sec=injection_rate.sample_interval_sec,
        )
