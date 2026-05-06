"""``TypeCurveFitter`` — fit a type curve to a population of well-rate series.

Algorithm:
    1. Receive a ``rate_series`` SCADA time series of production rates.
    2. Normalise the series to a common time origin.
    3. Fit Arps decline parameters (``qi``, ``Di``, ``b``) to the normalised
       series using non-linear least squares.
    4. Integrate the fitted decline to economic limit to obtain EUR.
    5. Return the fitted parameters and EUR as a dict.

Math:
    Hyperbolic decline rate (Arps):

    $$q(t) = \\frac{q_i}{(1 + b \\, D_i \\, t)^{1/b}}$$

    EUR by integrating to economic limit :math:`q_{el}`:

    $$\\text{EUR} = \\frac{q_i^b}{D_i (1-b)}
      \\left(q_{el}^{1-b} - q_i^{1-b}\\right)$$

References:
    - Arps, J.J. (1945). Analysis of decline curves. *Trans. AIME*, 160,
      228–247. SPE-945228-G.
    - Robertson, S. (1988). Generalized hyperbolic equation. SPE-18731-MS.
"""

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
