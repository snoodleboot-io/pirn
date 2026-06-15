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
      228-247. SPE-945228-G.
    - Fetkovich, M.J. (1980). Decline curve analysis using type curves.
      *JPT*, 32(6), 1065-1077. SPE-4629-PA.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from scipy.optimize import curve_fit

from pirn_oilgas.types.scada_payload import ScadaPayload

# Nominal decline initial guess: 15 %/year converted to per-day.
_di_init_day = 0.15 / 365.0
_b_init = 0.5  # mid-range hyperbolic exponent


class DeclineCurveAnalyzer(Knot):
    """Fit an Arps decline (exponential, hyperbolic, harmonic) to a series."""

    valid_methods: ClassVar[frozenset[str]] = frozenset({"exponential", "hyperbolic", "harmonic"})

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
        rate_series: ScadaPayload,
        method: str,
        **_: Any,
    ) -> dict[str, float]:
        """Fit the configured Arps decline model to the rate series and return the qi, di, and b parameters.

        Args:
            rate_series: ScadaPayload of historical production rates.
            method: One of ``exponential``, ``hyperbolic``, or ``harmonic``.

        Returns:
            Dict with keys ``qi`` (initial rate), ``di_per_year`` (nominal
            decline), and ``b`` (hyperbolic exponent).
        """
        if not isinstance(rate_series, ScadaPayload):
            raise TypeError("DeclineCurveAnalyzer: rate_series must be a ScadaPayload")
        if method not in self.valid_methods:
            raise ValueError(
                f"DeclineCurveAnalyzer: method must be one of {sorted(self.valid_methods)}"
            )

        rate_array = rate_series.values.astype(np.float64)
        if len(rate_array) < 2:
            return {
                "qi": float(rate_array[0]) if len(rate_array) == 1 else 0.0,
                "di_per_year": 0.0,
                "b": 0.0,
            }

        # Convert sample-index time to days using the SCADA channel interval
        time_days = (
            np.arange(len(rate_array), dtype=np.float64)
            * rate_series.series.sample_interval_sec
            / 86400.0
        )

        return await asyncio.to_thread(self._fit, rate_array, time_days, method)

    @staticmethod
    def _fit(rate_array: np.ndarray, time_days: np.ndarray, method: str) -> dict[str, float]:
        if method == "exponential":
            return DeclineCurveAnalyzer._fit_exponential(rate_array, time_days)
        if method == "harmonic":
            return DeclineCurveAnalyzer._fit_harmonic(rate_array, time_days)
        # hyperbolic: attempt curve_fit, fall back to exponential on failure
        return DeclineCurveAnalyzer._fit_hyperbolic(rate_array, time_days)

    @staticmethod
    def _fit_exponential(rate_array: np.ndarray, time_days: np.ndarray) -> dict[str, float]:
        log_q = np.log(rate_array + 1e-9)
        slope, intercept = np.polyfit(time_days, log_q, 1)
        qi = float(np.exp(intercept))
        di_day = float(-slope)
        # Convert per-day decline to per-year for the return contract
        di_annual = di_day * 365.0
        return {"qi": qi, "di_per_year": di_annual, "b": 0.0}

    @staticmethod
    def _fit_harmonic(rate_array: np.ndarray, time_days: np.ndarray) -> dict[str, float]:
        # Harmonic: q(t) = qi / (1 + di*t)  →  1/q = 1/qi + di/qi * t
        inv_q = 1.0 / (rate_array + 1e-9)
        slope, intercept = np.polyfit(time_days, inv_q, 1)
        qi = 1.0 / max(float(intercept), 1e-9)
        di_day = float(slope) * qi
        return {"qi": qi, "di_per_year": di_day * 365.0, "b": 1.0}

    @staticmethod
    def _fit_hyperbolic(rate_array: np.ndarray, time_days: np.ndarray) -> dict[str, float]:
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
            return {"qi": qi, "di_per_year": di_day * 365.0, "b": arps_b}
        except Exception:
            # Degrade gracefully to exponential when scipy cannot converge
            return DeclineCurveAnalyzer._fit_exponential(rate_array, time_days)
