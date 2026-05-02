"""``PisarenkoEstimator`` — Pisarenko harmonic decomposition."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class PisarenkoEstimator(Knot):
    """Pisarenko harmonic-decomposition frequency estimator.

    Production needs an eigen-decomposition-based estimator.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        sinusoid_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(sinusoid_count, int) or sinusoid_count <= 0:
            raise ValueError(
                "PisarenkoEstimator: sinusoid_count must be a positive integer"
            )
        self._sinusoid_count = sinusoid_count
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def sinusoid_count(self) -> int:
        return self._sinusoid_count

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        return {
            "signal_id": signal.signal_id,
            "sinusoid_count": self._sinusoid_count,
            "estimator": "pisarenko",
        }
