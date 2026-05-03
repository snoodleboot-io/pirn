"""``HurstExponentEstimator`` — long-range dependence / fractal estimator."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class HurstExponentEstimator(Knot):
    """Estimate the Hurst exponent (long-memory / self-similarity).

    Production needs ``nolds`` or a hand-rolled R/S analysis.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        method: str = "rs",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if method not in {"rs", "dfa", "wavelet"}:
            raise ValueError(
                "HurstExponentEstimator: method must be 'rs', 'dfa', or 'wavelet'"
            )
        self._method = method
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def method(self) -> str:
        return self._method

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        """Estimate the Hurst exponent of the signal using the configured method and return a result mapping.

        Args:
            signal: Time series signal to estimate long-range dependence from.

        Returns:
            Mapping containing ``signal_id``, ``method``, and ``estimator``.
        """
        return {
            "signal_id": signal.signal_id,
            "method": self._method,
            "estimator": "hurst",
        }
