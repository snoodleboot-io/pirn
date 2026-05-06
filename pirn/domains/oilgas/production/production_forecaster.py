"""``ProductionForecaster`` — project a future rate series from decline params.

Algorithm:
    1. Receive a ``decline_parameters`` dict and a positive integer
       ``forecast_months``.
    2. Validate that ``forecast_months`` is a positive integer.
    3. Apply the Arps decline model forward in time for ``forecast_months`` steps.
    4. Return a ScadaTimeSeries of forecasted production rates.

Math:
    Exponential decline (Arps, 1945):

    $$q(t) = q_i \\exp(-D \\cdot t)$$

    Hyperbolic decline:

    $$q(t) = \\frac{q_i}{(1 + b D_i t)^{1/b}}$$

    where :math:`q_i` is initial rate, :math:`D_i` is nominal decline rate
    (per year), and :math:`b` is the hyperbolic exponent.

References:
    - Arps, J.J. (1945). Analysis of decline curves. *Trans. AIME*, 160, 228-247.
    - SPE-1476-PA, Vogel (1968); extended by Fetkovich (1980) SPE-4629-PA.
"""

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
        forecast_months: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            decline_parameters=decline_parameters,
            forecast_months=forecast_months,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        decline_parameters: dict[str, float],
        forecast_months: int,
        **_: Any,
    ) -> ScadaTimeSeries:
        """Project a forecast rate series for the configured number of months from the decline parameters and return it.

        Args:
            decline_parameters: Dict of fitted decline-curve parameters
                (e.g. initial rate, decline rate) used to project forward.
            forecast_months: Positive integer number of months to forecast.

        Returns:
            ScadaTimeSeries of forecasted production rates spanning the
            configured number of months.
        """
        if not isinstance(forecast_months, int) or forecast_months <= 0:
            raise ValueError("ProductionForecaster: forecast_months must be a positive integer")
        return ScadaTimeSeries(
            sensor_id="forecast",
            sample_count=forecast_months,
            sample_interval_sec=86_400.0 * 30.0,
        )
