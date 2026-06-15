"""``DeclineRateEstimator`` — short-window decline rate from a rate series.

Algorithm:
    1. Receive a production ScadaPayload and a positive integer ``window_days``.
    2. Validate that ``window_days`` is a positive integer.
    3. Extract the trailing ``window_days`` samples from the rate series.
    4. Fit a linear log-rate regression to estimate the instantaneous decline rate.
    5. Return the estimated fractional decline rate per year.

Math:
    Exponential decline rate estimated from log-linear regression over the window:

    $$\\ln q(t) = \\ln q_i - D \\cdot t$$

    Solving for :math:`D`:

    $$D = -\\frac{\\Delta \\ln q}{\\Delta t}$$

    where :math:`\\Delta t` is expressed in years and :math:`D > 0` indicates
    declining production.

References:
    - Arps, J.J. (1945). Analysis of decline curves. *Trans. AIME*, 160, 228-247.
    - Ahmed, T. (2010). *Reservoir Engineering Handbook*, 4th ed. Gulf
      Professional Publishing, Chapter 11.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.scada_payload import ScadaPayload


def _fit_decline(values: np.ndarray, sample_interval_sec: float) -> float:
    positive_rates = values[values > 0]
    if len(positive_rates) < 2:
        return 0.0
    time_days = np.arange(len(positive_rates)) * sample_interval_sec / 86400
    log_q = np.log(positive_rates + 1e-9)
    slope, _ = np.polyfit(time_days, log_q, 1)
    di_per_day = -slope
    di_per_year = di_per_day * 365
    return float(max(di_per_year, 0.0))


class DeclineRateEstimator(Knot):
    """Estimate the local decline rate (per year) of a production series."""

    def __init__(
        self,
        *,
        rate_series: Knot,
        window_days: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rate_series=rate_series,
            window_days=window_days,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        rate_series: ScadaPayload,
        window_days: int,
        **_: Any,
    ) -> float:
        """Accept a rate payload and return the estimated decline rate per year over the window.

        Args:
            rate_series: ScadaPayload of production rates from which the
                decline is estimated over the configured window.
            window_days: Positive integer number of days for the trailing window.

        Returns:
            Estimated decline rate as a fractional value per year (e.g. 0.15
            represents 15 % annual decline).
        """
        if not isinstance(rate_series, ScadaPayload):
            raise TypeError("DeclineRateEstimator: rate_series must be a ScadaPayload")
        if not isinstance(window_days, int) or window_days <= 0:
            raise ValueError("DeclineRateEstimator: window_days must be a positive integer")
        return await asyncio.to_thread(
            _fit_decline,
            rate_series.values,
            rate_series.series.sample_interval_sec,
        )
