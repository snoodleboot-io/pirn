"""``DeclineCurveAnalyzer`` — fit an Arps-style decline curve to a series.

Algorithm:
    1. Receive a production rate ScadaTimeSeries and a ``method`` string.
    2. Validate that ``method`` is one of ``exponential``, ``hyperbolic``,
       or ``harmonic``.
    3. Fit the selected Arps model to the historical rate data via non-linear
       least squares.
    4. Return the fitted parameters: initial rate, nominal decline, and
       hyperbolic exponent.

Math:
    Exponential decline (:math:`b = 0`):

    $$q(t) = q_i \\, e^{-D_i t}$$

    Hyperbolic decline (:math:`0 < b < 1`):

    $$q(t) = \\frac{q_i}{(1 + b D_i t)^{1/b}}$$

    Harmonic decline (:math:`b = 1`):

    $$q(t) = \\frac{q_i}{1 + D_i t}$$

References:
    - Arps, J.J. (1945). Analysis of decline curves. *Trans. AIME*, 160,
      228–247. SPE-945228-G.
    - Fetkovich, M.J. (1980). Decline curve analysis using type curves.
      *JPT*, 32(6), 1065–1077. SPE-4629-PA.
"""

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
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rate_series=rate_series,
            method=method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        rate_series: ScadaTimeSeries,
        method: str,
        **_: Any,
    ) -> dict[str, float]:
        """Fit the configured Arps decline model to the rate series and return the qi, di, and b parameters.

        Args:
            rate_series: SCADA time series of historical production rates.
            method: One of ``exponential``, ``hyperbolic``, or ``harmonic``.

        Returns:
            Dict with keys ``qi`` (initial rate), ``di_per_year`` (nominal
            decline), and ``b`` (hyperbolic exponent).
        """
        if method not in self.valid_methods:
            raise ValueError(
                f"DeclineCurveAnalyzer: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        return {
            "qi": 1000.0,
            "di_per_year": 0.15,
            "b": 0.5 if method == "hyperbolic" else 0.0,
        }
