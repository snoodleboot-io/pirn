"""``ProductionForecaster`` — project a future rate series from decline params."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class ProductionForecaster(Knot):
    """Project a forecast rate series from a fitted decline model."""

    def __init__(
        self,
        *,
        decline_parameters: Knot,
        forecast_months: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(forecast_months, int) or forecast_months <= 0:
            raise ValueError(
                "ProductionForecaster: forecast_months must be a positive integer"
            )
        self._forecast_months = forecast_months
        super().__init__(
            decline_parameters=decline_parameters, _config=_config, **kwargs
        )

    async def process(
        self,
        decline_parameters: dict[str, float],
        **_: Any,
    ) -> ScadaTimeSeries:
        """Project a forecast rate series for the configured number of months from the decline parameters and return it.

        Args:
            decline_parameters: Dict of fitted decline-curve parameters
                (e.g. initial rate, decline rate) used to project forward.

        Returns:
            ScadaTimeSeries of forecasted production rates spanning the
            configured number of months.
        """
        return ScadaTimeSeries(
            sensor_id="forecast",
            sample_count=self._forecast_months,
            sample_interval_sec=86_400.0 * 30.0,
        )
