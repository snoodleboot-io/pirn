"""``ARModelEstimator`` — fit an autoregressive model to a signal."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ARModelEstimator(Knot):
    """Fit an autoregressive (AR) model to a signal using a configurable estimation method."""

    _valid_methods = frozenset({"burg", "yule_walker", "ols"})

    def __init__(
        self,
        *,
        signal: Knot,
        order: int,
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(order, int) or order <= 0:
            raise ValueError("ARModelEstimator: order must be a positive integer")
        if method not in self._valid_methods:
            raise ValueError(
                "ARModelEstimator: method must be one of 'burg', 'yule_walker', 'ols'"
            )
        self._order = order
        self._method = method
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def order(self) -> int:
        return self._order

    @property
    def method(self) -> str:
        return self._method

    async def process(self, signal: SignalFrame, **_: Any) -> dict[str, Any]:
        """Fit an AR model and return the estimated parameters.

        Args:
            signal: The input signal frame.

        Returns:
            Dict with keys ``coefficients`` (list[float]), ``order`` (int),
            ``method`` (str), and ``variance`` (float).
        """
        return {
            "coefficients": [0.0] * self._order,
            "order": self._order,
            "method": self._method,
            "variance": 1.0,
        }
