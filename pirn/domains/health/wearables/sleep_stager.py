"""``SleepStager`` — stage sleep epochs as wake / N1 / N2 / N3 / REM.

Production version uses YASA / a CNN classifier. This stub returns
the requested number of placeholder ``wake`` stages.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class SleepStager(Knot):
    """Stage sleep from a long PSG / single-channel EEG signal."""

    def __init__(
        self,
        *,
        signal: SignalFrame,
        epoch_length_sec: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError("SleepStager: signal must be a SignalFrame")
        if not isinstance(epoch_length_sec, (int, float)):
            raise TypeError(
                "SleepStager: epoch_length_sec must be numeric"
            )
        if float(epoch_length_sec) <= 0:
            raise ValueError(
                "SleepStager: epoch_length_sec must be positive"
            )
        self._signal = signal
        self._epoch_length = float(epoch_length_sec)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[str, ...]:
        total_sec = self._signal.samples_per_channel / max(
            self._signal.sample_rate_hz, 1.0
        )
        n_epochs = max(1, int(total_sec / self._epoch_length))
        return tuple("wake" for _ in range(n_epochs))
