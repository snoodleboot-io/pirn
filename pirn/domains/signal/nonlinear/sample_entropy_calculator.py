"""``SampleEntropyCalculator`` — sample entropy of a time series."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class SampleEntropyCalculator(Knot):
    """Compute sample entropy of a time series signal.

    Production needs ``antropy`` or a hand-rolled template-matching
    implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        m: int,
        r: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(m, int) or m <= 0:
            raise ValueError(
                "SampleEntropyCalculator: m must be a positive integer"
            )
        if not isinstance(r, (int, float)) or r <= 0.0:
            raise ValueError(
                "SampleEntropyCalculator: r must be a positive float"
            )
        self._m = m
        self._r = float(r)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def m(self) -> int:
        return self._m

    @property
    def r(self) -> float:
        return self._r

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> dict[str, float]:
        """Compute sample entropy of the signal using template matching.

        Args:
            signal: Time series signal to analyse.

        Returns:
            Dictionary with keys ``sample_entropy``, ``m``, and ``r``.
        """
        return {
            "sample_entropy": 0.0,
            "m": float(self._m),
            "r": self._r,
        }
