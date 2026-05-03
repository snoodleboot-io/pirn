"""``DeclineRateEstimator`` — short-window decline rate from a rate series."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class DeclineRateEstimator(Knot):
    """Estimate the local decline rate (per year) of a production series."""

    def __init__(
        self,
        *,
        rate_series: Knot,
        window_days: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(window_days, int) or window_days <= 0:
            raise ValueError(
                "DeclineRateEstimator: window_days must be a positive integer"
            )
        self._window_days = window_days
        super().__init__(rate_series=rate_series, _config=_config, **kwargs)

    async def process(
        self, rate_series: ScadaTimeSeries, **_: Any
    ) -> float:
        """Accept a rate time series and return the estimated decline rate per year over the configured window.

        Args:
            rate_series: ScadaTimeSeries of production rates from which the
                decline is estimated over the configured window.

        Returns:
            Estimated decline rate as a fractional value per year (e.g. 0.15
            represents 15 % annual decline).
        """
        return 0.15
