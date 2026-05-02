"""``OnsetDetector`` — note / event onset detection."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class OnsetDetector(Knot):
    """Detect onset times in an audio signal.

    Production needs ``librosa.onset``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        hop_length: int,
        threshold: float = 0.5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(hop_length, int) or hop_length <= 0:
            raise ValueError(
                "OnsetDetector: hop_length must be a positive integer"
            )
        if not isinstance(threshold, (int, float)) or threshold <= 0:
            raise ValueError("OnsetDetector: threshold must be positive")
        self._hop_length = hop_length
        self._threshold = float(threshold)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def hop_length(self) -> int:
        return self._hop_length

    @property
    def threshold(self) -> float:
        return self._threshold

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        return {
            "signal_id": signal.signal_id,
            "hop_length": self._hop_length,
            "threshold": self._threshold,
            "feature": "onsets",
        }
