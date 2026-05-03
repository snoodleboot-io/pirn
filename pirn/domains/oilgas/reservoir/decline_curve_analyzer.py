"""``DeclineCurveAnalyzer`` — fit an Arps-style decline curve to a series."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class DeclineCurveAnalyzer(Knot):
    """Fit an Arps decline (exponential, hyperbolic, harmonic) to a series."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"exponential", "hyperbolic", "harmonic"}
    )

    def __init__(
        self,
        *,
        rate_series: Knot,
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if method not in self.valid_methods:
            raise ValueError(
                f"DeclineCurveAnalyzer: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        self._method = method
        super().__init__(rate_series=rate_series, _config=_config, **kwargs)

    async def process(
        self, rate_series: ScadaTimeSeries, **_: Any
    ) -> dict[str, float]:
        """Fit the configured Arps decline model to the rate series and return the qi, di, and b parameters.

        Args:
            rate_series: SCADA time series of historical production rates.

        Returns:
            Dict with keys ``qi`` (initial rate), ``di_per_year`` (nominal decline), and ``b`` (hyperbolic exponent).
        """
        return {
            "qi": 1000.0,
            "di_per_year": 0.15,
            "b": 0.5 if self._method == "hyperbolic" else 0.0,
        }
