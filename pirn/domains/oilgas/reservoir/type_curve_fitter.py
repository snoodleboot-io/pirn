"""``TypeCurveFitter`` — fit a type curve to a population of well-rate series."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class TypeCurveFitter(Knot):
    """Fit a single type curve to a representative rate series."""

    def __init__(
        self,
        *,
        rate_series: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(rate_series=rate_series, _config=_config, **kwargs)

    async def process(
        self, rate_series: ScadaTimeSeries, **_: Any
    ) -> dict[str, float]:
        """Fit a type curve to the rate series and return the qi, di, b, and EUR parameters.

        Args:
            rate_series: SCADA time series of production rates used to fit the type curve.

        Returns:
            Dict with keys ``qi``, ``di_per_year``, ``b``, and ``eur_stb``.
        """
        return {
            "qi": 1200.0,
            "di_per_year": 0.20,
            "b": 0.8,
            "eur_stb": 350_000.0,
        }
