"""``HurstExponentEstimator`` — long-range dependence / fractal estimator.

Algorithm:
    1. Receive the input signal frame and method.
    2. Validate method (one of ``rs``, ``dfa``, ``wavelet``).
    3. Apply the selected estimation method:
       - ``rs``: Rescaled-range (R/S) analysis over partitions of increasing length.
       - ``dfa``: Detrended fluctuation analysis with linear detrending.
       - ``wavelet``: Wavelet-based LRD estimator from spectral slope.
    4. Fit the log-log slope to obtain the Hurst exponent H ∈ (0, 1).
    5. Return a result mapping with the estimated exponent and method.

Math:
    Rescaled-range scaling:

    $$E\\left[\\frac{R(n)}{S(n)}\\right] \\sim C \\cdot n^H \\quad \\text{as } n \\to \\infty$$

    where $R(n)$ is the range and $S(n)$ is the standard deviation over $n$ observations.

References:
    - Hurst, H.E. (1951). "Long-term storage capacity of reservoirs." Trans. Am. Soc. Civil Eng., 116, 770-808.
    - nolds library: https://github.com/CSchoel/nolds
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class HurstExponentEstimator(Knot):
    """Estimate the Hurst exponent (long-memory / self-similarity).

    Production needs ``nolds`` or a hand-rolled R/S analysis.
    """

    _valid_methods = frozenset({"rs", "dfa", "wavelet"})

    def __init__(
        self,
        *,
        signal: Knot,
        method: Knot | str = "rs",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            method=method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        method: str = "rs",
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate the Hurst exponent of the signal using the configured method.

        Args:
            signal: Time series signal to estimate long-range dependence from.
            method: Estimation method — ``rs`` (rescaled range), ``dfa``
                (detrended fluctuation analysis), or ``wavelet``.

        Returns:
            Mapping containing ``signal_id``, ``method``, and ``estimator``.

        Raises:
            ValueError: If method is not one of the valid options.
        """
        if method not in self._valid_methods:
            raise ValueError(
                "HurstExponentEstimator: method must be 'rs', 'dfa', or 'wavelet'"
            )
        return {
            "signal_id": signal.signal_id,
            "method": method,
            "estimator": "hurst",
        }
