"""``ProductionForecaster`` — project a future rate series from decline params.

Algorithm:
    1. Receive a ``decline_parameters`` dict and a positive integer
       ``forecast_months``.
    2. Validate that ``forecast_months`` is a positive integer.
    3. Apply the Arps decline model forward in time for ``forecast_months`` steps.
    4. Return a ScadaPayload of forecasted production rates.

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

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_payload import ScadaPayload
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

# One calendar month in seconds (30-day approximation standard in oil production).
_month_sec = 86_400.0 * 30.0


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
    ) -> ScadaPayload:
        """Project a forecast rate series for the configured number of months from the decline parameters and return it.

        Args:
            decline_parameters: Dict of fitted decline-curve parameters with
                keys ``qi``, ``di_per_year``, and ``b``.
            forecast_months: Positive integer number of months to forecast.

        Returns:
            ScadaPayload of forecasted production rates spanning the
            configured number of months.
        """
        if not isinstance(forecast_months, int) or forecast_months <= 0:
            raise ValueError("ProductionForecaster: forecast_months must be a positive integer")
        for key in ("qi", "di_per_year", "b"):
            if key not in decline_parameters:
                raise KeyError(
                    f"ProductionForecaster: decline_parameters missing required key '{key}'"
                )

        qi = float(decline_parameters["qi"])
        di_annual = float(decline_parameters["di_per_year"])
        b = float(decline_parameters["b"])

        q = await asyncio.to_thread(self._generate, qi, di_annual, b, forecast_months)

        series = ScadaTimeSeries(
            sensor_id="forecast",
            sample_count=forecast_months,
            sample_interval_sec=_month_sec,
        )
        return ScadaPayload(metadata=series, data=q)

    @staticmethod
    def _generate(qi: float, di_annual: float, b: float, n: int) -> np.ndarray:
        # Each step is one month; time in days for Arps formula
        t_days = np.arange(n, dtype=np.float64) * 30.0
        di_day = di_annual / 365.0

        if b < 1e-6:
            q = qi * np.exp(-di_day * t_days)
        else:
            q = qi * (1.0 + b * di_day * t_days) ** (-1.0 / b)

        return np.maximum(q, 0.0).astype(np.float64)
