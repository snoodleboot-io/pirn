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
      228-247. SPE-945228-G.
    - Robertson, S. (1988). Generalized hyperbolic equation. SPE-18731-MS.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy.optimize import curve_fit

from pirn_oilgas.types.scada_payload import ScadaPayload

# Typical economic abandonment rate for a single well (BOPD).
_q_aban = 1.0

# Nominal decline / exponent initial guesses (Fetkovich, 1980).
_di_init_day = 0.15 / 365.0
_b_init = 0.5


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

    async def process(self, rate_series: ScadaPayload, **_: Any) -> dict[str, float]:
        """Fit a type curve to the rate series and return the qi, di, b, and EUR parameters.

        Args:
            rate_series: ScadaPayload of production rates used to fit the type curve.

        Returns:
            Dict with keys ``qi``, ``di_per_year``, ``b``, and ``eur_stb``.
        """
        if not isinstance(rate_series, ScadaPayload):
            raise TypeError("TypeCurveFitter: rate_series must be a ScadaPayload")

        rate_array = rate_series.values.astype(np.float64)
        if len(rate_array) < 2:
            return {
                "qi": float(rate_array[0]) if len(rate_array) == 1 else 0.0,
                "di_per_year": 0.0,
                "b": 0.0,
                "eur_stb": 0.0,
            }

        time_days = (
            np.arange(len(rate_array), dtype=np.float64)
            * rate_series.series.sample_interval_sec
            / 86400.0
        )

        return await asyncio.to_thread(self._fit_and_integrate, rate_array, time_days)

    @staticmethod
    def _fit_and_integrate(rate_array: np.ndarray, time_days: np.ndarray) -> dict[str, float]:
        def hyperbolic(time_arr: np.ndarray, qi_: float, di_: float, arps_b: float) -> np.ndarray:
            return qi_ * (1.0 + arps_b * di_ * time_arr) ** (-1.0 / arps_b)

        qi0 = float(rate_array[0]) if rate_array[0] > 0 else 1.0
        try:
            popt, _ = curve_fit(
                hyperbolic,
                time_days,
                rate_array,
                p0=[qi0, _di_init_day, _b_init],
                bounds=([0.0, 1e-9, 1e-6], [np.inf, np.inf, 0.9999]),
                maxfev=5000,
            )
            qi, di_day, arps_b = float(popt[0]), float(popt[1]), float(popt[2])
        except Exception:
            # Exponential fallback
            log_q = np.log(rate_array + 1e-9)
            slope, intercept = np.polyfit(time_days, log_q, 1)
            qi = float(np.exp(intercept))
            di_day = float(-slope)
            arps_b = 0.0

        di_annual = di_day * 365.0

        if arps_b < 1e-6:
            # Exponential EUR: qi / di (days) integrated to abandonment
            eur = (
                qi
                / max(di_day, 1e-9)
                * (1.0 - np.exp(-di_day * np.log(qi / max(_q_aban, 1e-9)) / max(di_day, 1e-9)))
            )
        else:
            # Hyperbolic EUR: qi^arps_b / (di*(1-arps_b)) * (qi^(1-arps_b) - q_aban^(1-arps_b))
            # Robertson (1988) integrated Arps formula.
            eur = (qi**arps_b / (di_day * (1.0 - arps_b))) * (
                qi ** (1.0 - arps_b) - _q_aban ** (1.0 - arps_b)
            )

        eur = max(float(eur), 0.0)

        return {"qi": qi, "di_per_year": di_annual, "b": arps_b, "eur_stb": eur}
