"""``TimeFrequencyDecomposer`` — Morlet / Multitaper time-frequency analysis.

Production version uses ``mne.time_frequency.tfr_morlet``. This stub
validates inputs and returns an empty mapping ``frequency -> power``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class TimeFrequencyDecomposer(Knot):
    """Decompose a signal into time-frequency representations."""

    def __init__(
        self,
        *,
        signal: SignalFrame,
        frequencies_hz: Sequence[float],
        method: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal, SignalFrame):
            raise TypeError(
                "TimeFrequencyDecomposer: signal must be a SignalFrame"
            )
        if not isinstance(frequencies_hz, (list, tuple)):
            raise TypeError(
                "TimeFrequencyDecomposer: frequencies_hz must be list/tuple"
            )
        for freq in frequencies_hz:
            if not isinstance(freq, (int, float)) or float(freq) <= 0:
                raise ValueError(
                    "TimeFrequencyDecomposer: every frequency must be positive"
                )
        if method not in ("morlet", "multitaper", "stockwell"):
            raise ValueError(
                "TimeFrequencyDecomposer: method must be one of morlet/multitaper/stockwell"
            )
        self._signal = signal
        self._frequencies = tuple(float(f) for f in frequencies_hz)
        self._method = method
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[float, float]:
        return {freq: 0.0 for freq in self._frequencies}
